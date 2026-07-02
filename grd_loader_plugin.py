# -*- coding: utf-8 -*-
"""
Geosoft GRD Loader
A simple QGIS plugin to load Oasis Montaj (Geosoft) binary .grd grid
files as raster layers.
"""

import os

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsRasterLayer, QgsProject, Qgis

from .grd_loader_dialog import GrdLoaderDialog
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

        action = QAction(icon, "Load Geosoft GRD...", self.iface.mainWindow())
        action.triggered.connect(self.run)
        action.setEnabled(True)

        self.toolbar.addAction(action)
        self.iface.addPluginToRasterMenu(self.menu, action)

        self.actions.append(action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginRasterMenu(self.menu, action)
        del self.toolbar

    def run(self):
        dialog = GrdLoaderDialog(self.iface.mainWindow())
        if not dialog.exec_():
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
