# -*- coding: utf-8 -*-
"""
Batch dialog: pick multiple .grd files and/or a whole folder of them,
choose one shared CRS and output location, click OK.

All files added to the list are converted using the same CRS (the
CRS picker here is deliberately singular — there is no per-file CRS
override, since the whole point of batch mode is "apply one CRS to
everything").
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QListWidget,
    QAbstractItemView,
    QFileDialog,
    QDialogButtonBox,
    QMessageBox,
)
from qgis.gui import QgsProjectionSelectionWidget

GRD_EXTENSION = ".grd"


class BatchGrdLoaderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Convert Geosoft GRD Files")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        # --- Add files / add folder buttons ---
        add_row = QHBoxLayout()
        add_files_btn = QPushButton("Add Files...")
        add_files_btn.clicked.connect(self._add_files)
        add_row.addWidget(add_files_btn)

        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self._add_folder)
        add_row.addWidget(add_folder_btn)

        self.recurse_check = QCheckBox("Include subfolders (check before selecting folder)")
        add_row.addWidget(self.recurse_check)
        add_row.addStretch()
        layout.addLayout(add_row)

        # --- File list ---
        layout.addWidget(QLabel("Files queued for conversion:"))
        self.file_list = QListWidget()
        # Qt6 moved enum members under the enum class; use SelectionMode.
        try:
            self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        except AttributeError:
            # Fallback for older PyQt versions / shims that still expose the old name
            self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setMinimumHeight(160)
        layout.addWidget(self.file_list)

        list_btn_row = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        list_btn_row.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.file_list.clear)
        list_btn_row.addWidget(clear_btn)

        list_btn_row.addStretch()
        self.count_label = QLabel("0 file(s)")
        self.count_label.setStyleSheet("color: gray;")
        list_btn_row.addWidget(self.count_label)
        layout.addLayout(list_btn_row)

        self.file_list.model().rowsInserted.connect(self._update_count)
        self.file_list.model().rowsRemoved.connect(self._update_count)

        # --- Output folder row ---
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output folder (optional):"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Leave blank to save each .tif next to its source .grd"
        )
        output_row.addWidget(self.output_edit)
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self._browse_output_folder)
        output_row.addWidget(output_browse_btn)
        layout.addLayout(output_row)

        # --- CRS picker row (single, shared across the whole batch) ---
        crs_row = QHBoxLayout()
        crs_row.addWidget(QLabel("CRS for all files (optional):"))
        self.crs_widget = QgsProjectionSelectionWidget()
        crs_row.addWidget(self.crs_widget)
        layout.addLayout(crs_row)

        self.crs_hint = QLabel(
            "This CRS is applied to every file in the batch. If left unset,\n"
            "each file falls back to its own matching .grd.xml sidecar (if any)."
        )
        self.crs_hint.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.crs_hint)

        # --- Extra options ---
        self.skip_existing_check = QCheckBox(
            "Skip files whose output .tif already exists"
        )
        layout.addWidget(self.skip_existing_check)

        self.add_to_map_check = QCheckBox("Add converted layers to the map")
        self.add_to_map_check.setChecked(True)
        layout.addWidget(self.add_to_map_check)

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
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Adding / removing files
    # ------------------------------------------------------------------

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select GRD files",
            "",
            "Geosoft Grid Files (*.grd);;All Files (*)",
        )
        for path in paths:
            self._add_path(path)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return

        found = []
        if self.recurse_check.isChecked():
            for root, _dirs, files in os.walk(folder):
                for name in files:
                    if name.lower().endswith(GRD_EXTENSION):
                        found.append(os.path.join(root, name))
        else:
            for name in os.listdir(folder):
                full = os.path.join(folder, name)
                if os.path.isfile(full) and name.lower().endswith(GRD_EXTENSION):
                    found.append(full)

        if not found:
            QMessageBox.information(
                self,
                "Batch Convert Geosoft GRD Files",
                f"No .grd files were found in:\n{folder}"
                + ("" if self.recurse_check.isChecked() else "\n\n"
                   "Tip: check 'Include subfolders' to search recursively."),
            )
            return

        for path in sorted(found):
            self._add_path(path)

    def _add_path(self, path):
        """Add a path to the list, skipping duplicates."""
        existing = {
            self.file_list.item(i).text() for i in range(self.file_list.count())
        }
        if path not in existing:
            self.file_list.addItem(path)

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _update_count(self, *_args):
        n = self.file_list.count()
        self.count_label.setText(f"{n} file(s)")

    # ------------------------------------------------------------------
    # Output folder
    # ------------------------------------------------------------------

    def _browse_output_folder(self):
        start = self.output_edit.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", start
        )
        if folder:
            self.output_edit.setText(folder)

    # ------------------------------------------------------------------
    # Validation / accept
    # ------------------------------------------------------------------

    def _on_accept(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(
                self,
                "Batch Convert Geosoft GRD Files",
                "Add at least one .grd file or a folder before clicking OK.",
            )
            return

        output_folder = self.output_edit.text().strip()
        if output_folder and not os.path.isdir(output_folder):
            QMessageBox.critical(
                self,
                "Batch Convert Geosoft GRD Files",
                f"Output folder does not exist:\n{output_folder}",
            )
            return

        self.accept()

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def grd_files(self):
        return [self.file_list.item(i).text() for i in range(self.file_list.count())]

    def output_folder(self):
        return self.output_edit.text().strip()

    def selected_epsg(self):
        """Return the EPSG integer code if a CRS was chosen, else None.

        This single value is applied to every file in the batch.
        """
        crs = self.crs_widget.crs()
        if crs and crs.isValid():
            auth_id = crs.authid()  # e.g. "EPSG:28350"
            if auth_id.upper().startswith("EPSG:"):
                return auth_id.split(":")[1]
        return None

    def skip_existing(self):
        return self.skip_existing_check.isChecked()

    def add_to_map(self):
        return self.add_to_map_check.isChecked()
