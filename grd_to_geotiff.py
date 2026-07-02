# -*- coding: utf-8 -*-
"""
Convert a parsed Geosoft .grd grid into a GeoTIFF file using GDAL,
so it can be loaded into QGIS as a standard raster layer.
"""

import numpy as np

from osgeo import gdal, osr

from .grd_parser import load_grd, find_sidecar_xml, extract_epsg_from_xml


def convert_grd_to_geotiff(grd_path, tiff_path, epsg_code=None):
    """
    Parse a .grd file and write it out as a GeoTIFF.

    Parameters
    ----------
    grd_path : str
        Path to the source .grd file.
    tiff_path : str
        Destination path for the .tif output.
    epsg_code : int or str or None
        EPSG code to assign as the layer's CRS. If None, the function
        will try to auto-detect it from a sidecar .grd.xml file.

    Returns
    -------
    epsg_used : str or None
        The EPSG code that was actually written to the file (if any).
    """
    grid, header = load_grd(grd_path)

    n_rows, n_cols = grid.shape
    dx = header["spacing_e"]
    dy = header["spacing_v"]
    x0 = header["x_origin"]
    y0 = header["y_origin"]

    # y0 is the origin at the bottom-left (south); GDAL's GeoTransform
    # needs the top-left corner and a negative Y pixel size.
    y_top = y0 + dy * (n_rows - 1)

    geotransform = (x0, dx, 0, y_top, 0, -dy)

    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        tiff_path,
        n_cols,
        n_rows,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "TILED=YES"],
    )
    dataset.SetGeoTransform(geotransform)

    band = dataset.GetRasterBand(1)
    nodata = -3.4028235e38  # standard Float32 nodata sentinel
    filled = np.where(np.isnan(grid), nodata, grid).astype(np.float32)
    band.WriteArray(filled)
    band.SetNoDataValue(nodata)
    band.FlushCache()

    epsg_used = None
    if epsg_code is None:
        xml_path = find_sidecar_xml(grd_path)
        if xml_path:
            epsg_code = extract_epsg_from_xml(xml_path)

    if epsg_code:
        try:
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(epsg_code))
            dataset.SetProjection(srs.ExportToWkt())
            epsg_used = str(int(epsg_code))
        except Exception:
            epsg_used = None

    dataset.FlushCache()
    dataset = None

    return epsg_used
