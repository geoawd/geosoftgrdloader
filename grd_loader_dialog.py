# -*- coding: utf-8 -*-
"""
Simple dialog: pick a .grd file, choose where to save the .tif output,
optionally set a CRS, click OK.
"""

import os

from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
)
from qgis.gui import QgsProjectionSelectionWidget
from qgis.core import QgsCoordinateReferenceSystem


class GrdLoaderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Geosoft GRD File")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        # --- File picker row ---
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("GRD file:"))
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a .grd file...")
        self.file_edit.textChanged.connect(self._update_default_output_path)
        file_row.addWidget(self.file_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # --- Output GeoTIFF row ---
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Save as:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output .tif path...")
        output_row.addWidget(self.output_edit)
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(output_browse_btn)
        layout.addLayout(output_row)

        # --- CRS picker row ---
        crs_row = QHBoxLayout()
        crs_row.addWidget(QLabel("CRS (optional):"))
        self.crs_widget = QgsProjectionSelectionWidget()
        crs_row.addWidget(self.crs_widget)
        layout.addLayout(crs_row)

        self.crs_hint = QLabel(
            "If left unset, the plugin will try to detect the CRS from a\n"
            "matching .grd.xml file, otherwise the layer will be unprojected."
        )
        self.crs_hint.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.crs_hint)

        # --- OK / Cancel ---
        # Use Qt6 enum path if available, with fallback for older shims
        try:
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
        except AttributeError:
            buttons = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GRD file", "", "Geosoft Grid Files (*.grd);;All Files (*)"
        )
        if path:
            self.file_edit.setText(path)

    def _update_default_output_path(self, grd_path):
        """Auto-fill the output path as <grd folder>/<grd name>.tif."""
        grd_path = grd_path.strip()
        if not grd_path:
            return
        folder = os.path.dirname(grd_path)
        base_name = os.path.splitext(os.path.basename(grd_path))[0]
        default_output = os.path.join(folder, base_name + ".tif")
        self.output_edit.setText(default_output)

    def _browse_output(self):
        # Default the save dialog to whatever is currently in the field.
        start_path = self.output_edit.text().strip()
        if not start_path:
            grd_path = self.file_edit.text().strip()
            if grd_path:
                base_name = os.path.splitext(os.path.basename(grd_path))[0]
                start_path = base_name + ".tif"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save GeoTIFF As", start_path, "GeoTIFF (*.tif *.tiff)"
        )
        if path:
            if not path.lower().endswith((".tif", ".tiff")):
                path += ".tif"
            self.output_edit.setText(path)

    def selected_file(self):
        return self.file_edit.text().strip()

    def output_file(self):
        return self.output_edit.text().strip()

    def selected_epsg(self):
        """Return the EPSG integer code if a CRS was chosen, else None."""
        crs = self.crs_widget.crs()
        if crs and crs.isValid():
            auth_id = crs.authid()  # e.g. "EPSG:28350"
            if auth_id.upper().startswith("EPSG:"):
                return auth_id.split(":")[1]
        return None
