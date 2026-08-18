# -*- coding: utf-8 -*-
"""
Geosoft GRD Loader

A simple QGIS plugin to load Oasis Montaj (Geosoft) binary .grd grid
files as raster layers, either one at a time or in batch (a folder or
a multi-selection of files, all converted using the same CRS).
"""

import os

from qgis.PyQt.QtWidgets import QAction, QMessageBox, QProgressDialog
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsRasterLayer, QgsProject, Qgis

from .grd_loader_dialog import GrdLoaderDialog
from .batch_grd_loader_dialog import BatchGrdLoaderDialog
from .grd_parser import GrdParseError


class GeosoftGrdLoaderPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&Geosoft GRD Loader"
        self.toolbar = self.iface.addToolBar("Geosoft GRD Loader")
        self.toolbar.setObjectName("GeosoftGrdLoaderToolbar")

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()
        # Add icon for batch conversion
        icon_path_batch = os.path.join(os.path.dirname(__file__), "icon_batch.png")
        icon_batch = QIcon(icon_path_batch) if os.path.isfile(icon_path_batch) else QIcon()

        action = QAction(icon, "Load Geosoft GRD...", self.iface.mainWindow())
        action.triggered.connect(self.run)
        action.setEnabled(True)
        self.toolbar.addAction(action)
        self.iface.addPluginToRasterMenu(self.menu, action)
        self.actions.append(action)

        batch_action = QAction(
            icon_batch, "Batch Convert Geosoft GRD...", self.iface.mainWindow()
        )
        batch_action.triggered.connect(self.run_batch)
        batch_action.setEnabled(True)
        self.toolbar.addAction(batch_action)
        self.iface.addPluginToRasterMenu(self.menu, batch_action)
        self.actions.append(batch_action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginRasterMenu(self.menu, action)
        del self.toolbar

    # ------------------------------------------------------------------
    # Single-file workflow (unchanged)
    # ------------------------------------------------------------------

    def run(self):
        dialog = GrdLoaderDialog(self.iface.mainWindow())
        if not dialog.exec():
            return

        grd_path = dialog.selected_file()
        if not grd_path:
            QMessageBox.warning(
                self.iface.mainWindow(), "Geosoft GRD Loader", "No file was selected."
            )
            return

        if not os.path.isfile(grd_path):
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Geosoft GRD Loader",
                f"File not found:\n{grd_path}",
            )
            return

        tiff_path = dialog.output_file()
        if not tiff_path:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Geosoft GRD Loader",
                "No output .tif location was specified.",
            )
            return

        if not tiff_path.lower().endswith((".tif", ".tiff")):
            tiff_path += ".tif"

        output_dir = os.path.dirname(tiff_path)
        if output_dir and not os.path.isdir(output_dir):
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Geosoft GRD Loader",
                f"Output folder does not exist:\n{output_dir}",
            )
            return

        epsg_code = dialog.selected_epsg()
        base_name = os.path.splitext(os.path.basename(tiff_path))[0]

        try:
            # Import here so the module (and its GDAL dependency) is only
            # touched once the user actually tries to load a file.
            from .grd_to_geotiff import convert_grd_to_geotiff

            epsg_used = convert_grd_to_geotiff(grd_path, tiff_path, epsg_code)
        except GrdParseError as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Geosoft GRD Loader",
                f"Could not parse the GRD file:\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Geosoft GRD Loader",
                f"Unexpected error while loading the file:\n{e}",
            )
            return

        layer = QgsRasterLayer(tiff_path, base_name)
        if not layer.isValid():
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Geosoft GRD Loader",
                "The grid was converted but QGIS could not load the "
                "resulting raster layer.",
            )
            return

        QgsProject.instance().addMapLayer(layer)

        if epsg_used:
            msg = f"Loaded '{base_name}' with CRS EPSG:{epsg_used}."
        else:
            msg = (
                f"Loaded '{base_name}'. No CRS was set — you may want to "
                "assign one manually (Layer Properties > Source)."
            )
        self.iface.messageBar().pushMessage(
            "Geosoft GRD Loader", msg, level=Qgis.Info, duration=5
        )

    # ------------------------------------------------------------------
    # Batch workflow (new)
    # ------------------------------------------------------------------

    def run_batch(self):
        dialog = BatchGrdLoaderDialog(self.iface.mainWindow())
        if not dialog.exec():
            return

        grd_paths = dialog.grd_files()
        output_folder = dialog.output_folder() or None
        epsg_code = dialog.selected_epsg()
        skip_existing = dialog.skip_existing()
        add_to_map = dialog.add_to_map()

        # Import here so GDAL is only touched once a conversion is
        # actually requested.
        from .batch_convert import batch_convert

        total = len(grd_paths)
        progress = QProgressDialog(
            "Converting GRD files...", "Cancel", 0, total, self.iface.mainWindow()
        )
        progress.setWindowTitle("Batch Convert Geosoft GRD Files")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        def on_progress(index, count, current_path):
            progress.setLabelText(
                f"Converting {index + 1} of {count}:\n{os.path.basename(current_path)}"
            )
            progress.setValue(index)
            return not progress.wasCanceled()

        results = batch_convert(
            grd_paths,
            output_folder=output_folder,
            epsg_code=epsg_code,
            skip_existing=skip_existing,
            progress_callback=on_progress,
        )
        progress.setValue(total)

        succeeded = [r for r in results if r.success]
        skipped = [r for r in results if r.skipped]
        failed = [r for r in results if r.error]

        loaded_count = 0
        if add_to_map:
            for result in succeeded:
                base_name = os.path.splitext(os.path.basename(result.tiff_path))[0]
                layer = QgsRasterLayer(result.tiff_path, base_name)
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    loaded_count += 1
                else:
                    result.error = (
                        "Converted, but QGIS could not load the resulting "
                        "raster layer."
                    )
                    failed.append(result)

        summary_lines = [
            f"Converted: {len(succeeded)}/{len(results)}",
        ]
        if add_to_map:
            summary_lines.append(f"Added to map: {loaded_count}")
        if skipped:
            summary_lines.append(f"Skipped (already existed): {len(skipped)}")
        if failed:
            summary_lines.append(f"Failed: {len(failed)}")

        if epsg_code:
            summary_lines.append(f"CRS applied to batch: EPSG:{epsg_code}")

        if failed:
            detail_lines = [
                f"- {os.path.basename(r.grd_path)}: {r.error}" for r in failed
            ]
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Batch Convert Geosoft GRD Files",
                "\n".join(summary_lines) + "\n\nFailures:\n" + "\n".join(detail_lines),
            )
        else:
            self.iface.messageBar().pushMessage(
                "Geosoft GRD Loader",
                "; ".join(summary_lines),
                level=Qgis.Info,
                duration=6,
            )
