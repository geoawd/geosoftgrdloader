# -*- coding: utf-8 -*-
"""
Parser for Geosoft / Oasis Montaj (R) binary .grd grid files (Version 2 format).

Adapted from the open-source GRD reader originally written for the
Fatiando a Terra / Harmonica project (BSD-3-Clause), with compression
support contributed by the Loop3D project (MIT). Simplified here for use
as a standalone GDAL-free parser inside a QGIS plugin.

References:
    https://help.seequent.com/Oasis-montaj/9.9/en/Content/ss/glossary/grid_file_format__grd.htm
    https://github.com/fatiando/harmonica
    https://github.com/Loop3D/geosoft_grid
"""

import array
import os
import struct
import zlib

import numpy as np

# Valid "ES" (element size) values. Anything > 1024 means the grid data
# is compressed; subtract 1024 to get the true element size.
VALID_ELEMENT_SIZES = (1, 2, 4, 8, 1024 + 1, 1024 + 2, 1024 + 4, 1024 + 8)

# Dummy / no-data sentinel values used by Geosoft for each element type.
DUMMIES = {
    "b": -127,
    "B": 255,
    "h": -32767,
    "H": 65535,
    "i": -2147483647,
    "I": 4294967295,
    "f": -1e32,
    "d": -1e32,
}


class GrdParseError(Exception):
    """Raised when a .grd file cannot be parsed."""


def load_grd(path):
    """
    Read a Geosoft binary .grd (v2) file.

    Returns
    -------
    grid : 2D numpy.ndarray (float64), shape (rows, cols), row 0 = north
    header : dict of parsed header fields
    """
    with open(path, "rb") as f:
        raw_header = f.read(512)
        if len(raw_header) < 512:
            raise GrdParseError("File is too small to contain a valid GRD header.")
        header = _read_header(raw_header)
        _check_supported(header)

        data_type = _get_data_type(header["n_bytes_per_element"], header["sign_flag"])

        body = f.read()

    if header["n_bytes_per_element"] > 1024:
        body = _decompress_grid(body)

    values = array.array(data_type, body)
    values = np.array(values, dtype=np.float64)
    values = _remove_dummies(values, data_type)

    # Apply scale/offset: Z = raw / data_factor + base_value
    if header["data_factor"] == 0:
        raise GrdParseError("Invalid data scaling factor (ZMULT) of 0 in header.")
    values = values / header["data_factor"] + header["base_value"]

    # Reshape according to storage order (KX)
    n_e, n_v = header["shape_e"], header["shape_v"]
    if header["ordering"] == 1:
        shape = (n_v, n_e)
        order = "C"
    else:  # -1
        shape = (n_e, n_v)
        order = "F"

    expected = shape[0] * shape[1]
    if values.size != expected:
        raise GrdParseError(
            f"Grid data size mismatch: expected {expected} values, "
            f"found {values.size}. The file may be corrupted or use an "
            f"unsupported variant of the GRD format."
        )

    grid = values.reshape(shape, order=order)

    # Grid rows currently go south -> north (row 0 = south, matching the
    # Y-origin at the bottom-left). Raster convention (and GDAL) expects
    # row 0 = north, so flip vertically.
    grid = np.flipud(grid)

    return grid, header


def _read_header(b):
    header = {}

    ES, SF, NE, NV, KX = struct.unpack_from("<5i", b, 0)
    header.update(
        n_bytes_per_element=ES,
        sign_flag=SF,
        shape_e=NE,
        shape_v=NV,
        ordering=KX,
    )

    DE, DV, X0, Y0, ROT = struct.unpack_from("<5d", b, 20)
    header.update(
        spacing_e=DE,
        spacing_v=DV,
        x_origin=X0,
        y_origin=Y0,
        rotation=ROT,
    )

    ZBASE, ZMULT = struct.unpack_from("<2d", b, 60)
    header.update(base_value=ZBASE, data_factor=ZMULT)

    return header


def _check_supported(header):
    if header["ordering"] not in (-1, 1):
        raise GrdParseError(
            f"Unsupported grid ordering (KX={header['ordering']}); "
            "only +1 and -1 are supported."
        )
    if header["sign_flag"] == 3:
        raise GrdParseError("Colour grids are not supported.")
    if header["n_bytes_per_element"] not in VALID_ELEMENT_SIZES:
        raise GrdParseError(
            f"Unsupported element size (ES={header['n_bytes_per_element']})."
        )
    if header["rotation"] != 0:
        raise GrdParseError(
            "Rotated grids are not supported by this simple loader."
        )


def _get_data_type(n_bytes_per_element, sign_flag):
    es = n_bytes_per_element
    if es > 1024:
        es -= 1024

    if es == 1:
        return "b" if sign_flag == 1 else "B"
    if es == 2:
        return "h" if sign_flag == 1 else "H"
    if es == 4:
        if sign_flag == 2:
            return "f"
        return "i" if sign_flag == 1 else "I"
    if es == 8:
        return "d"
    raise GrdParseError(f"Unhandled element size: {es}")


def _remove_dummies(values, data_type):
    if data_type in ("f", "d"):
        values[values <= DUMMIES[data_type]] = np.nan
    else:
        values[values == DUMMIES[data_type]] = np.nan
    return values


def _decompress_grid(compressed):
    """
    Decompress a Geosoft-compressed grid body.

    Despite the header's COMP_TYPE nominally indicating LZRW1, Geosoft
    grids are in practice zlib-compressed in blocks.
    """
    (n_blocks,) = struct.unpack_from("<i", compressed, 8)
    # vectors_per_block at offset 12 is unused here
    block_offsets = array.array("q", compressed[16 : 16 + n_blocks * 8])
    block_sizes = array.array(
        "i", compressed[16 + n_blocks * 8 : 16 + n_blocks * 8 + n_blocks * 4]
    )

    chunks = []
    for i in range(n_blocks):
        start = block_offsets[i] - 512 + 16
        end = block_sizes[i] + block_offsets[i] - 512
        chunks.append(zlib.decompress(compressed[start:end]))
    return b"".join(chunks)


def find_sidecar_xml(grd_path):
    """Return path to the .grd.xml metadata file if it exists, else None."""
    candidate = grd_path + ".xml"
    if os.path.isfile(candidate):
        return candidate
    return None


def extract_epsg_from_xml(xml_path):
    """
    Best-effort extraction of a 'wellknown_epsg' code from a Geosoft
    .grd.xml sidecar file. Returns an EPSG code as a string, or None.
    """
    try:
        with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "wellknown_epsg=" in line:
                    cleaned = line.replace("&quot;", '"')
                    parts = cleaned.split('wellknown_epsg="')
                    if len(parts) > 1:
                        code = parts[1].split('"')[0].strip()
                        if code.isdigit():
                            return code
    except OSError:
        pass
    return None
