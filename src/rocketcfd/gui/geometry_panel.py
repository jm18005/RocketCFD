"""Shared 3D-model-load/units/scale control."""
from __future__ import annotations

from pathlib import Path

import trimesh
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from rocketcfd.geometry import GeometryNotWatertightError, PanelMesh, ensure_watertight, load_model, rotate_mesh, scale_mesh, to_panel_mesh
from rocketcfd.gui.tooltips import (
    BBOX_LABEL_TOOLTIP,
    ENABLE_ROTATION_TOOLTIP,
    LOAD_MODEL_TOOLTIP,
    MESH_SCALE_TOOLTIP,
    ROTATE_X_TOOLTIP,
    ROTATE_Y_TOOLTIP,
    ROTATE_Z_TOOLTIP,
)
from rocketcfd.gui.units import LENGTH_UNITS, to_base
from rocketcfd.gui.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, labeled_row

MODEL_FILE_DIALOG_FILTER = (
    "3D model files (*.stl *.obj *.ply *.step *.stp *.iges *.igs);;"
    "Mesh files (*.stl *.obj *.ply);;CAD files (*.step *.stp *.iges *.igs);;All files (*)"
)


class GeometryPanel(QWidget):
    """Loads/repairs a 3D model (mesh or CAD) and rebuilds its PanelMesh whenever the
    file, unit, or scale factor changes; emits mesh_changed so the owning window can
    sync its own state."""

    mesh_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.panel_mesh: PanelMesh | None = None
        self.model_name: str = ""
        self._raw_mesh: trimesh.Trimesh | None = None
        self._geometry_load_status: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        browse_button = QPushButton("Load model...", self)
        browse_button.setToolTip(LOAD_MODEL_TOOLTIP)
        browse_button.clicked.connect(self._on_browse_model)
        self.stl_unit_combo = NoScrollComboBox(self)
        self.stl_unit_combo.addItems(list(LENGTH_UNITS.keys()))
        self.stl_unit_combo.setCurrentText("m")
        self.stl_unit_combo.currentTextChanged.connect(self._on_stl_unit_changed)
        self.mesh_scale_spin = NoScrollDoubleSpinBox(self)
        self.mesh_scale_spin.setButtonSymbols(NoScrollDoubleSpinBox.ButtonSymbols.NoButtons)
        self.mesh_scale_spin.setDecimals(6)  # noqa: 34 (scale factor needs sub-unity precision)
        self.mesh_scale_spin.setRange(1e-6, 1e6)
        self.mesh_scale_spin.setValue(1.0)
        self.mesh_scale_spin.setToolTip(MESH_SCALE_TOOLTIP)
        self.mesh_scale_spin.valueChanged.connect(self._on_mesh_scale_changed)
        self.rotate_x_spin = self._build_rotation_spin(ROTATE_X_TOOLTIP)
        self.rotate_y_spin = self._build_rotation_spin(ROTATE_Y_TOOLTIP)
        self.rotate_z_spin = self._build_rotation_spin(ROTATE_Z_TOOLTIP)
        self.status_label = QLabel("No model loaded.", self)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.status_label.setCursor(Qt.CursorShape.IBeamCursor)
        self.bbox_label = QLabel("", self)
        self.bbox_label.setObjectName("bboxLabel")
        self.bbox_label.setWordWrap(True)
        self.bbox_label.setToolTip(BBOX_LABEL_TOOLTIP)
        self.bbox_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.bbox_label.setCursor(Qt.CursorShape.IBeamCursor)

        self.enable_rotation_checkbox = QCheckBox("Enable manual rotation", self)
        self.enable_rotation_checkbox.setToolTip(ENABLE_ROTATION_TOOLTIP)
        self.enable_rotation_checkbox.toggled.connect(self._on_enable_rotation_toggled)

        self.rotation_section = QWidget(self)
        rotation_layout = QVBoxLayout(self.rotation_section)
        rotation_layout.setContentsMargins(0, 0, 0, 0)
        rotation_layout.addLayout(labeled_row("Rotate about X", self.rotate_x_spin))
        rotation_layout.addLayout(labeled_row("Rotate about Y", self.rotate_y_spin))
        rotation_layout.addLayout(labeled_row("Rotate about Z", self.rotate_z_spin))
        self.rotation_section.setVisible(False)

        layout.addWidget(browse_button)
        layout.addLayout(labeled_row("Model file units", self.stl_unit_combo))
        layout.addLayout(labeled_row("Mesh scale factor", self.mesh_scale_spin))
        layout.addWidget(self.enable_rotation_checkbox)
        layout.addWidget(self.rotation_section)
        layout.addWidget(self.status_label)
        layout.addWidget(self.bbox_label)

    def _build_rotation_spin(self, tooltip: str) -> NoScrollDoubleSpinBox:
        spin = NoScrollDoubleSpinBox(self)
        spin.setButtonSymbols(NoScrollDoubleSpinBox.ButtonSymbols.NoButtons)
        spin.setRange(-180.0, 180.0)
        spin.setSuffix(" deg")
        spin.setValue(0.0)
        spin.setToolTip(tooltip)
        spin.valueChanged.connect(self._on_rotation_changed)
        return spin

    def rotation_deg(self) -> tuple[float, float, float]:
        return (self.rotate_x_spin.value(), self.rotate_y_spin.value(), self.rotate_z_spin.value())

    def _reset_rotation(self) -> None:
        for spin in (self.rotate_x_spin, self.rotate_y_spin, self.rotate_z_spin):
            spin.blockSignals(True)
            spin.setValue(0.0)
            spin.blockSignals(False)

    def _on_browse_model(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        path, _ = QFileDialog.getOpenFileName(self, "Load model", "", MODEL_FILE_DIALOG_FILTER)
        if path:
            self.load_model(path)

    def load_model(self, path: str) -> None:
        raw_mesh = load_model(path)
        try:
            repaired_mesh, report = ensure_watertight(raw_mesh)
        except GeometryNotWatertightError as exc:
            self._raw_mesh = None
            self.status_label.setText(f"{path}. {exc}")
            return
        self._raw_mesh = repaired_mesh
        self.model_name = Path(path).stem
        self._reset_rotation()

        status = "Mesh was already watertight." if report.was_watertight else f"Mesh was repaired to watertight using {report.method}."
        self._geometry_load_status = f"{path}. {status}"
        self._rebuild_scaled_mesh()

    def _on_stl_unit_changed(self, _label: str) -> None:  # noqa: 21 (Qt slot signature)
        if self._raw_mesh is not None:
            self._rebuild_scaled_mesh()

    def _on_mesh_scale_changed(self, _value: float) -> None:  # noqa: 21 (Qt slot signature)
        if self._raw_mesh is not None:
            self._rebuild_scaled_mesh()

    def _on_rotation_changed(self, _value: float) -> None:  # noqa: 21 (Qt slot signature)
        if self._raw_mesh is not None:
            self._rebuild_scaled_mesh()

    def _on_enable_rotation_toggled(self, checked: bool) -> None:
        self.rotation_section.setVisible(checked)

    def _rebuild_scaled_mesh(self) -> None:
        if self._raw_mesh is None:
            return
        unit = LENGTH_UNITS[self.stl_unit_combo.currentText()]
        scale_factor = to_base(1.0, unit, "m") * self.mesh_scale_spin.value()
        scaled_mesh = scale_mesh(self._raw_mesh, scale_factor)
        oriented_mesh = rotate_mesh(scaled_mesh, self.rotation_deg())
        self.panel_mesh = to_panel_mesh(oriented_mesh)
        self.status_label.setText(f"{self._geometry_load_status}\n{self.panel_mesh.panel_count} panels.")
        self._update_bbox_label()
        self.mesh_changed.emit()

    def _update_bbox_label(self) -> None:
        if self.panel_mesh is None:
            self.bbox_label.setText("")
            return
        xmin, xmax, ymin, ymax, zmin, zmax = self.panel_mesh.bounds()
        length, width, height = xmax - xmin, ymax - ymin, zmax - zmin
        self.bbox_label.setText(
            f"Bounding box: Length (X) {length:.3g} m, Width (Y) {width:.3g} m, Height (Z) {height:.3g} m"
        )
