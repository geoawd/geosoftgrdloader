# -*- coding: utf-8 -*-
"""
Batch conversion helper.

Wraps the existing single-file grd_to_geotiff.convert_grd_to_geotiff()
call in a loop over many .grd files, applying the *same* CRS to every
file in the batch. A single failing file does not stop the rest of the
batch -- failures are collected and reported back to the caller.
"""

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .grd_parser import GrdParseError


@dataclass
class BatchResult:
    grd_path: str
    tiff_path: Optional[str] = None
    epsg_used: Optional[str] = None
    skipped: bool = False
    error: Optional[str] = None

    @property
    def success(self):
        return self.error is None and not self.skipped


def default_output_path(grd_path, output_folder=None):
    """
    Work out the destination .tif path for a given .grd file.

    If output_folder is given, the .tif is placed there (flat, using
    just the source file's base name). Otherwise it is written
    alongside the source .grd file, matching the single-file plugin's
    default behaviour.
    """
    base_name = os.path.splitext(os.path.basename(grd_path))[0]
    if output_folder:
        return os.path.join(output_folder, base_name + ".tif")
    return os.path.join(os.path.dirname(grd_path), base_name + ".tif")


def batch_convert(
    grd_paths: List[str],
    output_folder: Optional[str] = None,
    epsg_code: Optional[str] = None,
    skip_existing: bool = False,
    progress_callback: Optional[Callable[[int, int, str], bool]] = None,
) -> List[BatchResult]:
    """
    Convert a list of .grd files to GeoTIFF using one shared CRS.

    Parameters
    ----------
    grd_paths : list of str
        Paths to source .grd files.
    output_folder : str or None
        If set, every output .tif is written into this single folder.
        If None, each .tif is written next to its source .grd file.
    epsg_code : int or str or None
        EPSG code applied to *every* file in the batch. If None, each
        file falls back to its own .grd.xml sidecar (if present),
        exactly like the single-file workflow.
    skip_existing : bool
        If True, files whose destination .tif already exists are
        skipped rather than overwritten.
    progress_callback : callable(index, total, current_path) -> bool
        Optional callback invoked before each file is processed.
        Return False to cancel the remaining batch.

    Returns
    -------
    list of BatchResult
        One entry per input file, recording success, skip, or error.
    """
    # Imported here so GDAL is only touched once a conversion is
    # actually requested (mirrors the single-file plugin's lazy import).
    from .grd_to_geotiff import convert_grd_to_geotiff

    results = []
    total = len(grd_paths)

    for index, grd_path in enumerate(grd_paths):
        if progress_callback is not None:
            keep_going = progress_callback(index, total, grd_path)
            if keep_going is False:
                break

        result = BatchResult(grd_path=grd_path)

        if not os.path.isfile(grd_path):
            result.error = "File not found."
            results.append(result)
            continue

        tiff_path = default_output_path(grd_path, output_folder)
        result.tiff_path = tiff_path

        if skip_existing and os.path.isfile(tiff_path):
            result.skipped = True
            results.append(result)
            continue

        dest_dir = os.path.dirname(tiff_path)
        if dest_dir and not os.path.isdir(dest_dir):
            result.error = f"Output folder does not exist: {dest_dir}"
            results.append(result)
            continue

        try:
            # The same epsg_code (or None) is passed for every file,
            # which is what enforces "one shared CRS for the batch".
            result.epsg_used = convert_grd_to_geotiff(grd_path, tiff_path, epsg_code)
        except GrdParseError as e:
            result.error = f"Parse error: {e}"
        except Exception as e:
            result.error = f"Unexpected error: {e}"

        results.append(result)

    return results
