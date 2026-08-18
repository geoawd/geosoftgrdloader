# Geosoft GRD Loader — QGIS Plugin

A minimal QGIS plugin that loads Oasis Montaj® (Geosoft) binary `.grd`
grid files (Version 2 format) directly into QGIS as raster layers.

## What it does

1. You pick a `.grd` file and (optionally) a CRS.
2. The plugin parses the binary grid (including zlib-compressed grids),
   converts it to a GeoTIFF in a temp folder, and adds it to QGIS as a
   raster layer.

That's it — no import options, no multi-step wizard.

## Installing

1. Zip the `geosoft_grd_loader` folder (the folder itself must be at the
   top level of the zip, e.g. `geosoft_grd_loader/__init__.py` inside
   `geosoft_grd_loader.zip`).
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the zip file and click **Install Plugin**.
4. Enable "Geosoft GRD Loader" if it isn't already active.

Alternatively, copy the `geosoft_grd_loader` folder directly into your
QGIS profile's `python/plugins` directory, then enable it from the
Plugin Manager.

## Using it

1. Click the toolbar icon (or **Raster menu → Geosoft GRD Loader → Load
   Geosoft GRD...**).
2. Browse to your `.grd` file. The **Save as** field auto-fills with the
   same name and folder as the source file, using a `.tif` extension
   (e.g. `survey_mag.grd` → `survey_mag.tif`). Change it via **Browse...**
   if you want a different name or location.
3. If a matching `yourfile.grd.xml` sidecar exists with a
   `wellknown_epsg` entry, the CRS is detected automatically. Otherwise,
   pick a CRS from the dropdown (optional — you can also assign a CRS
   later in Layer Properties).
4. Click **OK**. The GeoTIFF is written to the chosen location and
   loaded as a raster layer — no separate "save" step needed afterward.


## Batch conversion
1. Click **Raster menu → Geosoft GRD Loader → Batch Convert Geosoft
   GRD...**.
2. Use **Add Files...** and/or **Add Folder...** (with **Include
   subfolders** if needed) to build up the list of `.grd` files to
   convert. Use **Remove Selected** / **Clear All** to edit the list.
3. Optionally set an output folder — otherwise each `.tif` lands next to
   its source `.grd`.
4. Optionally pick a CRS. It's applied to **every** file in the batch.
5. Optionally check **Skip files whose output .tif already exists** to
   avoid re-converting files you've already processed.
6. Click **OK** and watch the progress dialog. A summary appears when
   it's done.

## Notes / limitations

- Supports Geosoft GRD **Version 2** binary files (`ES`, `SF`, `NE`,
  `NV`, `KX` header layout), including zlib-compressed grids.
- Rotated grids (`ROT != 0`) are not supported by this simple version.
- Colour grids are not supported.
- No-data cells (Geosoft "dummy" values) are converted to NaN / raster
  nodata.

## Credits

The binary format parsing logic is adapted from the open-source GRD
reader originally developed for the
[Fatiando a Terra / Harmonica](https://github.com/fatiando/harmonica)
project (BSD-3-Clause), with compression handling contributed by the
[Loop3D project](https://github.com/Loop3D/geosoft_grid) (MIT). Both are
gratefully acknowledged — a full-featured version of this idea already
exists as the [Loop3D `grd_loader`](https://github.com/Loop3D/grd_loader)
plugin, which also supports xml sidecar CRS detection and is worth
checking out if you need more features than this simple version offers.
