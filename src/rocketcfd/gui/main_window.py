"""Automation panel: builds a meshed OpenFOAM case, runs a flight-condition sweep, plots
and visualizes results. This is RocketCFD's primary working surface."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from pyvistaqt import QtInteractor

from rocketcfd.ansys_compare import compare_to_openfoam, parse_ansys_csv
from rocketcfd.atmosphere import us_standard_atmosphere
from rocketcfd.flow import SEA_LEVEL_TEMPERATURE, FlowCondition
from rocketcfd.gas import speed_of_sound
from rocketcfd.geometry import PanelMesh
from rocketcfd.gui.control_panel_mixins import ReferenceControlsMixin, SweepStatusMixin
from rocketcfd.gui.geometry_panel import GeometryPanel
from rocketcfd.gui.mesh_preview import load_mesh_boundary_surface
from rocketcfd.gui.openfoam_results import (
    PLOT_X_QUANTITIES,
    RESULT_HEADERS,
    RESULT_QUANTITIES,
    export_case_results_csv,
    populate_case_table,
)
from rocketcfd.gui.plotting import MplCanvas, draw_line_plot
from rocketcfd.gui.surface_fields import SURFACE_SCALAR_FIELDS, load_case_surface
from rocketcfd.gui.sweep_axis_row import SweepAxisRow
from rocketcfd.gui.sweep_variables import SWEEP_VARIABLES
from rocketcfd.gui.tooltips import (
    ALTITUDE_TOOLTIP,
    ANSYS_IMPORT_TOOLTIP,
    APPLY_ATMOSPHERE_TOOLTIP,
    AUTO_DETECT_BASHRC_TOOLTIP,
    BACKGROUND_CELL_COUNT_TOOLTIP,
    BASHRC_TOOLTIP,
    BOUNDARY_LAYERS_TOOLTIP,
    CASE_ROOT_BROWSE_TOOLTIP,
    CASE_ROOT_TOOLTIP,
    CASE_SELECT_TOOLTIP,
    DISTRO_TOOLTIP,
    DOWNSTREAM_DISTANCE_TOOLTIP,
    EXECUTION_MODE_TOOLTIP,
    EXPORT_CSV_TOOLTIP,
    FINAL_LAYER_THICKNESS_TOOLTIP,
    GROUND_AXIS_TOOLTIP,
    GROUND_EFFECT_TOOLTIP,
    GROUND_SIDE_TOOLTIP,
    IMPORT_RESULTS_TOOLTIP,
    LAYER_EXPANSION_TOOLTIP,
    MACH_CEILING_TOOLTIP,
    MACH_INPUT_TOOLTIP,
    MAX_ITERATIONS_TOOLTIP,
    MAX_NON_ORTHOGONALITY_TOOLTIP,
    MAX_SKEWNESS_TOOLTIP,
    MESH_PRESET_TOOLTIP,
    MESH_QUALITY_GATE_TOOLTIP,
    MOMENT_REF_BOX_TOOLTIP,
    MOMENT_REF_CENTROID_TOOLTIP,
    MOMENT_REF_X_TOOLTIP,
    MOMENT_REF_Y_TOOLTIP,
    MOMENT_REF_Z_TOOLTIP,
    N_PROCESSORS_TOOLTIP,
    PLOT_MODE_TOOLTIP,
    PLOT_QUANTITY_TOOLTIP,
    PLOT_X_AXIS_TOOLTIP,
    PREVIEW_MESH_TOOLTIP,
    REF_AREA_TOOLTIP,
    REF_DIMS_BOX_TOOLTIP,
    REF_DIMS_OVERRIDE_TOOLTIP,
    REF_LENGTH_TOOLTIP,
    RESIDUAL_FIELD_TOOLTIP,
    RESIDUAL_TOOLTIP,
    RUN_OPENFOAM_TOOLTIP,
    SHOW_COORDS_TOOLTIP,
    SHOW_DOMAIN_BOX_TOOLTIP,
    SHOW_FLOW_TOOLTIP,
    SHOW_GEOMETRY_BBOX_TOOLTIP,
    SHOW_WIND_TOOLTIP,
    SIDE_DISTANCE_TOOLTIP,
    SURFACE_REFINEMENT_MAX_TOOLTIP,
    SURFACE_REFINEMENT_MIN_TOOLTIP,
    SYMMETRY_AXIS_TOOLTIP,
    SYMMETRY_OFFSET_TOOLTIP,
    SYMMETRY_PLANE_TOOLTIP,
    TARGET_Y_PLUS_TOOLTIP,
    TOP_DISTANCE_TOOLTIP,
    TURBULENCE_INTENSITY_TOOLTIP,
    TURBULENCE_MODEL_TOOLTIP,
    UPSTREAM_DISTANCE_TOOLTIP,
    USE_CACHE_TOOLTIP,
    USE_TARGET_Y_PLUS_TOOLTIP,
    VIEW_SCALAR_TOOLTIP,
    WIND_DIRECTION_TOOLTIP,
    WIND_ELEVATION_TOOLTIP,
    WIND_SPEED_TOOLTIP,
)
from rocketcfd.gui.units import AREA_UNITS, LENGTH_UNITS, VELOCITY_UNITS
from rocketcfd.gui.viewport import add_bounding_box, add_domain_box, panel_mesh_to_polydata, render_scalar_field
from rocketcfd.gui.volume_fields import VELOCITY_MAGNITUDE_FIELD, flow_path_traces, load_case_volume, velocity_magnitude_slice
from rocketcfd.gui.widgets import CollapsibleSection, NoScrollComboBox, NoScrollDoubleSpinBox, UnitValueBox, labeled_row
from rocketcfd.openfoam.case_result import (
    OpenFoamCaseResult,
    ensure_mesh,
    find_case_roots,
    import_case_results,
    load_convergence_history,
    run_openfoam_sweep,
)
from rocketcfd.openfoam.execution import ExecutionBackend, NativeLinuxExecutionBackend, WslExecutionBackend
from rocketcfd.openfoam.results_parser import parse_residual_history
from rocketcfd.openfoam.runner import find_openfoam_bashrc, find_openfoam_bashrc_native, list_wsl_distros, solve_log_filename
from rocketcfd.openfoam.settings import (
    EXECUTION_MODES,
    EXECUTION_NATIVE_LINUX,
    EXECUTION_WSL,
    MESH_PRESET_CUSTOM,
    MESH_PRESET_MEDIUM,
    MESH_PRESET_NAMES,
    TURBULENCE_MODELS,
    GroundPlane,
    MeshSettings,
    NativeLinuxSettings,
    SolverSettings,
    SymmetryPlane,
    WslSettings,
    mesh_settings_for_preset,
    validate_domain_planes,
)
from rocketcfd.openfoam.templates import background_cell_counts, domain_bounds, location_in_mesh
from rocketcfd.solver_selection import DEFAULT_MACH_CEILING, HARD_MACH_LIMIT
from rocketcfd.sweep import build_conditions

# Each combination of swept values is a full mesh+solve round trip, so the axis count is
# capped well below sweep.py's unlimited N-D support to keep a run's case count sane by default.
MAX_SWEPT_VARIABLES = 3
FLOW_AXIS_KEYS = ["velocity", "alpha_deg", "beta_deg", "density", "temperature"]
FLOW_AXIS_LABELS = {
    "velocity": "Velocity (m/s)",
    "alpha_deg": "Alpha (deg)",
    "beta_deg": "Beta (deg)",
    "density": "Density (kg/m^3)",
    "temperature": "Temperature (K)",
}
PLOT_MODE_SWEEP = "Sweep"
PLOT_MODE_CONVERGENCE = "Convergence (single case)"
PLOT_MODE_RESIDUALS = "Residuals"
VIEW_MODE_GEOMETRY = "Geometry"
VIEW_MODE_VELOCITY_SLICE = "Velocity magnitude (slice)"
VIEW_MODE_FLOW_TRACES = "Flow-path traces"
LIVE_RESIDUAL_REFRESH_MS = 2000


def _int_spin(minimum: int, maximum: int, value: int, parent: QWidget) -> NoScrollDoubleSpinBox:
    spin = NoScrollDoubleSpinBox(parent)
    spin.setDecimals(0)  # noqa: 34 (genuinely integer-valued: cell/iteration/processor counts)
    spin.setButtonSymbols(NoScrollDoubleSpinBox.ButtonSymbols.NoButtons)
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    return spin


class OpenFoamSweepWorker(QThread):
    """Runs mesh generation + the flow-condition sweep off the GUI thread."""

    log = Signal(str)
    progress = Signal(int, int)
    case_finished = Signal(object)
    case_started = Signal(str, Path, str)
    succeeded = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        panel_mesh: PanelMesh,
        conditions: list[FlowCondition],
        moment_ref: np.ndarray,
        ground_plane: GroundPlane | None,
        mesh_settings: MeshSettings,
        solver_settings: SolverSettings,
        execution: ExecutionBackend,
        reference_area: float | None,
        reference_length: float | None,
        model_name: str,
        symmetry_planes: tuple[SymmetryPlane, ...],
        use_cache: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._args = (
            panel_mesh, conditions, moment_ref, ground_plane, mesh_settings, solver_settings, execution,
            reference_area, reference_length,
        )
        self._model_name = model_name
        self._symmetry_planes = symmetry_planes
        self._use_cache = use_cache

    def run(self) -> None:  # noqa: 21 (QThread override, invoked by Qt via .start())
        try:
            results = run_openfoam_sweep(
                *self._args,
                on_log=self.log.emit,
                on_progress=self.progress.emit,
                model_name=self._model_name,
                on_case_result=self.case_finished.emit,
                on_case_started=self.case_started.emit,
                symmetry_planes=self._symmetry_planes,
                use_cache=self._use_cache,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(results)


class MeshPreviewWorker(QThread):
    """Runs blockMesh/snappyHexMesh only (no solving) off the GUI thread, for the
    "preview the actual mesh before running" action."""

    log = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        panel_mesh: PanelMesh,
        ground_plane: GroundPlane | None,
        mesh_settings: MeshSettings,
        execution: ExecutionBackend,
        symmetry_planes: tuple[SymmetryPlane, ...],
        max_mach: float,
        use_cache: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._args = (panel_mesh, ground_plane, mesh_settings, execution)
        self._symmetry_planes = symmetry_planes
        self._max_mach = max_mach
        self._use_cache = use_cache

    def run(self) -> None:  # noqa: 21 (QThread override, invoked by Qt via .start())
        try:
            mesh_dir, _mesh_hash = ensure_mesh(
                *self._args, on_log=self.log.emit, symmetry_planes=self._symmetry_planes, max_mach=self._max_mach,
                use_cache=self._use_cache,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(mesh_dir)


class ImportSearchWorker(QThread):
    """Recursively searches a directory tree for OpenFOAM result cases off the GUI thread."""

    found = Signal(list)
    failed = Signal(str)

    def __init__(self, directory: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._directory = directory

    def run(self) -> None:  # noqa: 21 (QThread override, invoked by Qt via .start())
        try:
            roots = find_case_roots(self._directory)
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        self.found.emit(roots)


class MainWindow(QWidget, ReferenceControlsMixin, SweepStatusMixin):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.panel_mesh: PanelMesh | None = None
        self.case_results: list[OpenFoamCaseResult] = []
        self._sweep_thread: OpenFoamSweepWorker | None = None
        self._import_thread: ImportSearchWorker | None = None
        self._mesh_preview_thread: MeshPreviewWorker | None = None
        self._import_directory: str = ""
        self._live_case_log: Path | None = None
        self._residual_timer = QTimer(self)
        self._residual_timer.setInterval(LIVE_RESIDUAL_REFRESH_MS)
        self._residual_timer.timeout.connect(self._on_residual_timer_tick)

        self._build_ui()

    def _build_ui(self) -> None:
        control_scroll = QScrollArea(self)
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        control_panel = self._build_control_panel()
        control_scroll.setWidget(control_panel)
        control_scroll.setMinimumWidth(control_panel.minimumSizeHint().width() + 20)

        splitter = QSplitter(self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(control_scroll)
        splitter.addWidget(self._build_view_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 1060])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        intro_label = QLabel(
            "1. Load your rocket model.  2. Set flight conditions below.  3. Click Run.\n"
            "Sensible defaults are already filled in -- hover any field for what it does. "
            "Sections marked with an arrow are optional advanced settings.",
            panel,
        )
        intro_label.setWordWrap(True)
        intro_label.setObjectName("introLabel")
        layout.addWidget(intro_label)

        geometry_box = QGroupBox("1. Rocket model", panel)
        geometry_layout = QVBoxLayout(geometry_box)
        self.geometry_panel = GeometryPanel(geometry_box)
        self.geometry_panel.mesh_changed.connect(self._on_mesh_changed)
        self.geometry_status_label = QLabel("", geometry_box)
        self.geometry_status_label.setWordWrap(True)
        self.geometry_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.geometry_status_label.setCursor(Qt.CursorShape.IBeamCursor)
        self.show_bbox_checkbox = QCheckBox("Show geometry bounding box", geometry_box)
        self.show_bbox_checkbox.setToolTip(SHOW_GEOMETRY_BBOX_TOOLTIP)
        self.show_bbox_checkbox.toggled.connect(self._on_view_option_toggled)
        geometry_layout.addWidget(self.geometry_panel)
        geometry_layout.addWidget(self.geometry_status_label)
        geometry_layout.addWidget(self.show_bbox_checkbox)
        layout.addWidget(geometry_box)

        flow_box = QGroupBox("2. Flight conditions", panel)
        flow_layout = QVBoxLayout(flow_box)
        flow_layout.setSpacing(10)
        flow_hint_label = QLabel(
            f"Single value = fixed. List/range = swept (see the field's tooltip for syntax); "
            f"at most {MAX_SWEPT_VARIABLES} fields can be swept in one run.",
            flow_box,
        )
        flow_hint_label.setWordWrap(True)
        flow_hint_label.setObjectName("hintLabel")
        flow_layout.addWidget(flow_hint_label)
        self.rows: dict[str, SweepAxisRow] = {}
        for key in FLOW_AXIS_KEYS:
            row = SweepAxisRow(key, flow_box)
            self.rows[key] = row
            flow_layout.addLayout(labeled_row(SWEEP_VARIABLES[key].label, row))
            if key == "velocity":
                mach_row = SweepAxisRow("mach", flow_box)
                mach_row.setEnabled(False)
                self.rows["mach"] = mach_row
                flow_layout.addLayout(labeled_row(SWEEP_VARIABLES["mach"].label, mach_row))
                self.mach_input_checkbox = QCheckBox("Specify Mach instead of velocity", flow_box)
                self.mach_input_checkbox.setToolTip(MACH_INPUT_TOOLTIP)
                self.mach_input_checkbox.toggled.connect(self._on_mach_input_toggled)
                flow_layout.addWidget(self.mach_input_checkbox)
        self.altitude_row = SweepAxisRow("altitude", flow_box)
        altitude_label = QLabel("Altitude", flow_box)
        altitude_label.setToolTip(ALTITUDE_TOOLTIP)
        flow_layout.addLayout(labeled_row(altitude_label, self.altitude_row))
        apply_atmosphere_button = QPushButton("Apply ISA atmosphere", flow_box)
        apply_atmosphere_button.setToolTip(APPLY_ATMOSPHERE_TOOLTIP)
        apply_atmosphere_button.clicked.connect(self._on_apply_atmosphere)
        flow_layout.addWidget(apply_atmosphere_button)

        self.wind_speed_spin = UnitValueBox("m/s", VELOCITY_UNITS, "m/s", 0.0, 1e4, 0.0, flow_box, tooltip=WIND_SPEED_TOOLTIP)
        self.wind_direction_spin = NoScrollDoubleSpinBox(flow_box)
        self.wind_direction_spin.setRange(0.0, 360.0)
        self.wind_direction_spin.setToolTip(WIND_DIRECTION_TOOLTIP)
        self.wind_elevation_spin = NoScrollDoubleSpinBox(flow_box)
        self.wind_elevation_spin.setRange(-90.0, 90.0)
        self.wind_elevation_spin.setToolTip(WIND_ELEVATION_TOOLTIP)
        flow_layout.addLayout(labeled_row("Wind speed", self.wind_speed_spin))
        flow_layout.addLayout(labeled_row("Wind direction (deg)", self.wind_direction_spin))
        flow_layout.addLayout(labeled_row("Wind elevation (deg)", self.wind_elevation_spin))

        self.ground_effect_checkbox = QCheckBox("Model ground effect (pad transients)", flow_box)
        self.ground_effect_checkbox.setToolTip(GROUND_EFFECT_TOOLTIP)
        self.ground_effect_checkbox.toggled.connect(self._on_ground_effect_toggled)
        flow_layout.addWidget(self.ground_effect_checkbox)
        self.ground_axis_combo = NoScrollComboBox(flow_box)
        self.ground_axis_combo.addItems(["X", "Y", "Z"])
        self.ground_axis_combo.setCurrentText("Z")
        self.ground_axis_combo.setEnabled(False)
        self.ground_axis_combo.setToolTip(GROUND_AXIS_TOOLTIP)
        self.ground_axis_combo.currentTextChanged.connect(self._on_view_option_toggled)
        self.ground_side_combo = NoScrollComboBox(flow_box)
        self.ground_side_combo.addItems(["Min", "Max"])
        self.ground_side_combo.setCurrentText("Min")
        self.ground_side_combo.setEnabled(False)
        self.ground_side_combo.setToolTip(GROUND_SIDE_TOOLTIP)
        self.ground_side_combo.currentTextChanged.connect(self._on_view_option_toggled)
        flow_layout.addLayout(labeled_row("Ground plane axis", self.ground_axis_combo))
        flow_layout.addLayout(labeled_row("Ground plane side", self.ground_side_combo))

        self.symmetry_checkboxes: list[QCheckBox] = []
        self.symmetry_axis_combos: list[NoScrollComboBox] = []
        self.symmetry_offset_spins: list[UnitValueBox] = []
        for index, default_axis in enumerate(("Y", "Z")):
            checkbox = QCheckBox(f"Model symmetry plane {index + 1}", flow_box)
            checkbox.setToolTip(SYMMETRY_PLANE_TOOLTIP)
            checkbox.toggled.connect(self._on_symmetry_toggled)
            axis_combo = NoScrollComboBox(flow_box)
            axis_combo.addItems(["X", "Y", "Z"])
            axis_combo.setCurrentText(default_axis)
            axis_combo.setEnabled(False)
            axis_combo.setToolTip(SYMMETRY_AXIS_TOOLTIP)
            axis_combo.currentTextChanged.connect(self._on_view_option_toggled)
            offset_spin = UnitValueBox("m", LENGTH_UNITS, "m", -1e6, 1e6, 0.0, flow_box, tooltip=SYMMETRY_OFFSET_TOOLTIP)
            offset_spin.setEnabled(False)
            offset_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
            flow_layout.addWidget(checkbox)
            flow_layout.addLayout(labeled_row("Axis", axis_combo))
            flow_layout.addLayout(labeled_row("Offset", offset_spin))
            self.symmetry_checkboxes.append(checkbox)
            self.symmetry_axis_combos.append(axis_combo)
            self.symmetry_offset_spins.append(offset_spin)

        self.show_flow_checkbox = QCheckBox("Show flow direction", flow_box)
        self.show_flow_checkbox.setToolTip(SHOW_FLOW_TOOLTIP)
        self.show_flow_checkbox.toggled.connect(self._on_view_option_toggled)
        flow_layout.addWidget(self.show_flow_checkbox)
        self.show_wind_checkbox = QCheckBox("Show wind / total flow direction", flow_box)
        self.show_wind_checkbox.setToolTip(SHOW_WIND_TOOLTIP)
        self.show_wind_checkbox.toggled.connect(self._on_view_option_toggled)
        flow_layout.addWidget(self.show_wind_checkbox)
        layout.addWidget(flow_box)

        reference_box = QGroupBox("Moment reference", panel)
        reference_box.setToolTip(MOMENT_REF_BOX_TOOLTIP)
        reference_layout = QVBoxLayout(reference_box)
        self.moment_ref_centroid_button = QPushButton("Use mesh centroid", reference_box)
        self.moment_ref_centroid_button.setCheckable(True)
        self.moment_ref_centroid_button.setChecked(True)
        self.moment_ref_centroid_button.setToolTip(MOMENT_REF_CENTROID_TOOLTIP)
        self.moment_ref_centroid_button.toggled.connect(self._on_moment_ref_centroid_toggled)
        reference_layout.addWidget(self.moment_ref_centroid_button)
        self.ref_x_spin = UnitValueBox("m", LENGTH_UNITS, "m", -1e6, 1e6, 0.0, reference_box, tooltip=MOMENT_REF_X_TOOLTIP)
        self.ref_y_spin = UnitValueBox("m", LENGTH_UNITS, "m", -1e6, 1e6, 0.0, reference_box, tooltip=MOMENT_REF_Y_TOOLTIP)
        self.ref_z_spin = UnitValueBox("m", LENGTH_UNITS, "m", -1e6, 1e6, 0.0, reference_box, tooltip=MOMENT_REF_Z_TOOLTIP)
        self.ref_x_spin.setEnabled(False)
        self.ref_y_spin.setEnabled(False)
        self.ref_z_spin.setEnabled(False)
        reference_layout.addLayout(labeled_row("X", self.ref_x_spin))
        reference_layout.addLayout(labeled_row("Y", self.ref_y_spin))
        reference_layout.addLayout(labeled_row("Z", self.ref_z_spin))
        self.show_coords_checkbox = QCheckBox("Show coordinate system", reference_box)
        self.show_coords_checkbox.setToolTip(SHOW_COORDS_TOOLTIP)
        self.show_coords_checkbox.toggled.connect(self._on_view_option_toggled)
        reference_layout.addWidget(self.show_coords_checkbox)
        layout.addWidget(reference_box)

        ref_dims_box = QGroupBox("Reference area / length", panel)
        ref_dims_box.setToolTip(REF_DIMS_BOX_TOOLTIP)
        ref_dims_layout = QVBoxLayout(ref_dims_box)
        ref_dims_note = QLabel("Auto-computed from your model's frontal area. Only override if you know why.", ref_dims_box)
        ref_dims_note.setWordWrap(True)
        ref_dims_layout.addWidget(ref_dims_note)
        ref_dims_section = CollapsibleSection("Override reference area / length", ref_dims_box)
        self.ref_dims_override_checkbox = QCheckBox("Override auto (frontal-area-derived) values", ref_dims_box)
        self.ref_dims_override_checkbox.setToolTip(REF_DIMS_OVERRIDE_TOOLTIP)
        self.ref_dims_override_checkbox.toggled.connect(self._on_ref_dims_override_toggled)
        self.ref_area_spin = UnitValueBox("m**2", AREA_UNITS, "m^2", 0.0, 1e9, 1.0, ref_dims_box, tooltip=REF_AREA_TOOLTIP)
        self.ref_length_spin = UnitValueBox("m", LENGTH_UNITS, "m", 0.0, 1e6, 1.0, ref_dims_box, tooltip=REF_LENGTH_TOOLTIP)
        ref_dims_section.addWidget(self.ref_dims_override_checkbox)
        ref_dims_section.addLayout(labeled_row("Reference area", self.ref_area_spin))
        ref_dims_section.addLayout(labeled_row("Reference length", self.ref_length_spin))
        ref_dims_layout.addWidget(ref_dims_section)
        layout.addWidget(ref_dims_box)
        self._on_ref_dims_override_toggled(False)

        layout.addWidget(self._build_mesh_settings_box(panel))
        layout.addWidget(self._build_solver_settings_box(panel))
        layout.addWidget(self._build_execution_settings_box(panel))

        self.run_button = QPushButton("3. Run", panel)
        self.run_button.setObjectName("primaryAction")
        self.run_button.setToolTip(RUN_OPENFOAM_TOOLTIP)
        self.run_button.clicked.connect(self._on_run)
        layout.addWidget(self.run_button)

        self.sweep_progress = QProgressBar(panel)
        self.sweep_progress.setRange(0, 1)
        self.sweep_progress.setValue(0)
        self.sweep_progress.setFormat("%v / %m case(s) (%p%)")
        self.sweep_progress.setTextVisible(True)
        layout.addWidget(self.sweep_progress)

        layout.addStretch(1)

        self.rows["alpha_deg"].values_edit.textChanged.connect(lambda _text: self._refresh_viewport())
        self.rows["beta_deg"].values_edit.textChanged.connect(lambda _text: self._refresh_viewport())
        self.rows["velocity"].values_edit.textChanged.connect(lambda _text: self._refresh_viewport())
        self.rows["mach"].values_edit.textChanged.connect(lambda _text: self._refresh_viewport())
        self.rows["temperature"].values_edit.textChanged.connect(lambda _text: self._refresh_viewport())
        self.wind_speed_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        self.wind_direction_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        self.wind_elevation_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        self.ref_x_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        self.ref_y_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        self.ref_z_spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        return panel

    def _build_mesh_settings_box(self, parent: QWidget) -> QGroupBox:
        defaults = MeshSettings()
        self._applying_mesh_preset = False
        box = QGroupBox("Mesh settings", parent)
        mesh_layout = QVBoxLayout(box)
        self.mesh_preset_combo = NoScrollComboBox(box)
        self.mesh_preset_combo.addItems([*MESH_PRESET_NAMES, MESH_PRESET_CUSTOM])
        self.mesh_preset_combo.setToolTip(MESH_PRESET_TOOLTIP)
        self.mesh_preset_combo.currentTextChanged.connect(self._on_mesh_preset_changed)
        mesh_layout.addLayout(labeled_row("Mesh density preset", self.mesh_preset_combo))

        self.show_domain_box_checkbox = QCheckBox("Preview mesh domain in 3D view", box)
        self.show_domain_box_checkbox.setChecked(True)
        self.show_domain_box_checkbox.setToolTip(SHOW_DOMAIN_BOX_TOOLTIP)
        self.show_domain_box_checkbox.toggled.connect(self._on_view_option_toggled)
        mesh_layout.addWidget(self.show_domain_box_checkbox)
        self.domain_info_label = QLabel("", box)
        self.domain_info_label.setWordWrap(True)
        self.domain_info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        mesh_layout.addWidget(self.domain_info_label)

        self.preview_mesh_button = QPushButton("Preview mesh", box)
        self.preview_mesh_button.setToolTip(PREVIEW_MESH_TOOLTIP)
        self.preview_mesh_button.clicked.connect(self._on_preview_mesh)
        mesh_layout.addWidget(self.preview_mesh_button)

        self.mesh_advanced_section = CollapsibleSection("Advanced mesh parameters", box)
        mesh_layout.addWidget(self.mesh_advanced_section)
        mesh_layout = self.mesh_advanced_section

        self.upstream_spin = NoScrollDoubleSpinBox(box)
        self.upstream_spin.setRange(1.0, 50.0)
        self.upstream_spin.setValue(defaults.upstream_lengths)
        self.upstream_spin.setToolTip(UPSTREAM_DISTANCE_TOOLTIP)
        self.downstream_spin = NoScrollDoubleSpinBox(box)
        self.downstream_spin.setRange(1.0, 50.0)
        self.downstream_spin.setValue(defaults.downstream_lengths)
        self.downstream_spin.setToolTip(DOWNSTREAM_DISTANCE_TOOLTIP)
        self.side_spin = NoScrollDoubleSpinBox(box)
        self.side_spin.setRange(1.0, 50.0)
        self.side_spin.setValue(defaults.side_lengths)
        self.side_spin.setToolTip(SIDE_DISTANCE_TOOLTIP)
        self.top_spin = NoScrollDoubleSpinBox(box)
        self.top_spin.setRange(1.0, 50.0)
        self.top_spin.setValue(defaults.top_lengths)
        self.top_spin.setToolTip(TOP_DISTANCE_TOOLTIP)
        self.background_cell_count_spin = _int_spin(1, 200, defaults.background_cell_count, box)
        self.background_cell_count_spin.setToolTip(BACKGROUND_CELL_COUNT_TOOLTIP)
        self.refine_min_spin = _int_spin(0, 10, defaults.surface_refinement_min, box)
        self.refine_min_spin.setToolTip(SURFACE_REFINEMENT_MIN_TOOLTIP)
        self.refine_max_spin = _int_spin(0, 10, defaults.surface_refinement_max, box)
        self.refine_max_spin.setToolTip(SURFACE_REFINEMENT_MAX_TOOLTIP)
        self.boundary_layers_spin = _int_spin(0, 30, defaults.n_boundary_layers, box)
        self.boundary_layers_spin.setToolTip(BOUNDARY_LAYERS_TOOLTIP)
        self.layer_expansion_spin = NoScrollDoubleSpinBox(box)
        self.layer_expansion_spin.setRange(1.0, 2.0)
        self.layer_expansion_spin.setValue(defaults.boundary_layer_expansion_ratio)
        self.layer_expansion_spin.setToolTip(LAYER_EXPANSION_TOOLTIP)
        self.use_target_y_plus_checkbox = QCheckBox("Size first layer to target y+", box)
        self.use_target_y_plus_checkbox.setChecked(defaults.use_target_y_plus)
        self.use_target_y_plus_checkbox.setToolTip(USE_TARGET_Y_PLUS_TOOLTIP)
        self.use_target_y_plus_checkbox.toggled.connect(self._on_use_target_y_plus_toggled)
        self.target_y_plus_spin = NoScrollDoubleSpinBox(box)
        self.target_y_plus_spin.setRange(0.01, 500.0)
        self.target_y_plus_spin.setValue(defaults.target_y_plus)
        self.target_y_plus_spin.setToolTip(TARGET_Y_PLUS_TOOLTIP)
        self.final_layer_thickness_spin = NoScrollDoubleSpinBox(box)
        self.final_layer_thickness_spin.setRange(0.01, 1.0)
        self.final_layer_thickness_spin.setValue(defaults.final_layer_thickness_ratio)
        self.final_layer_thickness_spin.setToolTip(FINAL_LAYER_THICKNESS_TOOLTIP)

        mesh_layout.addLayout(labeled_row("Upstream distance (x body length)", self.upstream_spin))
        mesh_layout.addLayout(labeled_row("Downstream distance (x body length)", self.downstream_spin))
        mesh_layout.addLayout(labeled_row("Side distance (x body length)", self.side_spin))
        mesh_layout.addLayout(labeled_row("Top distance (x body length)", self.top_spin))
        mesh_layout.addLayout(labeled_row("Background cells along body length", self.background_cell_count_spin))
        mesh_layout.addLayout(labeled_row("Surface refinement (min level)", self.refine_min_spin))
        mesh_layout.addLayout(labeled_row("Surface refinement (max level)", self.refine_max_spin))
        mesh_layout.addLayout(labeled_row("Boundary layers", self.boundary_layers_spin))
        mesh_layout.addLayout(labeled_row("Boundary layer expansion ratio", self.layer_expansion_spin))
        mesh_layout.addWidget(self.use_target_y_plus_checkbox)
        mesh_layout.addLayout(labeled_row("Target y+", self.target_y_plus_spin))
        mesh_layout.addLayout(labeled_row("Final layer thickness ratio", self.final_layer_thickness_spin))
        self._on_use_target_y_plus_toggled(defaults.use_target_y_plus)

        self._applying_mesh_preset = True
        self.mesh_preset_combo.setCurrentText(MESH_PRESET_MEDIUM)
        self._applying_mesh_preset = False

        for spin in (
            self.background_cell_count_spin, self.refine_min_spin, self.refine_max_spin, self.boundary_layers_spin,
            self.target_y_plus_spin,
        ):
            spin.valueChanged.connect(lambda _value: self._on_mesh_setting_manually_changed())
        self.use_target_y_plus_checkbox.toggled.connect(lambda _checked: self._on_mesh_setting_manually_changed())

        self.mesh_quality_gate_checkbox = QCheckBox("Require checkMesh to pass before solving", box)
        self.mesh_quality_gate_checkbox.setChecked(defaults.require_mesh_quality_pass)
        self.mesh_quality_gate_checkbox.setToolTip(MESH_QUALITY_GATE_TOOLTIP)
        mesh_layout.addWidget(self.mesh_quality_gate_checkbox)
        self.max_non_ortho_spin = NoScrollDoubleSpinBox(box)
        self.max_non_ortho_spin.setRange(0.0, 89.0)
        self.max_non_ortho_spin.setValue(defaults.max_non_orthogonality)
        self.max_non_ortho_spin.setToolTip(MAX_NON_ORTHOGONALITY_TOOLTIP)
        self.max_skewness_spin = NoScrollDoubleSpinBox(box)
        self.max_skewness_spin.setRange(0.0, 20.0)
        self.max_skewness_spin.setValue(defaults.max_skewness)
        self.max_skewness_spin.setToolTip(MAX_SKEWNESS_TOOLTIP)
        mesh_layout.addLayout(labeled_row("Max non-orthogonality (deg)", self.max_non_ortho_spin))
        mesh_layout.addLayout(labeled_row("Max skewness", self.max_skewness_spin))

        for spin in (
            self.upstream_spin, self.downstream_spin, self.side_spin, self.top_spin, self.background_cell_count_spin,
        ):
            spin.valueChanged.connect(lambda _value: self._refresh_viewport())
        return box

    def _on_mesh_preset_changed(self, preset: str) -> None:
        if preset == MESH_PRESET_CUSTOM:
            return
        settings = mesh_settings_for_preset(preset)
        self._applying_mesh_preset = True
        self.background_cell_count_spin.setValue(settings.background_cell_count)
        self.refine_min_spin.setValue(settings.surface_refinement_min)
        self.refine_max_spin.setValue(settings.surface_refinement_max)
        self.boundary_layers_spin.setValue(settings.n_boundary_layers)
        self.target_y_plus_spin.setValue(settings.target_y_plus)
        self._applying_mesh_preset = False

    def _on_mesh_setting_manually_changed(self) -> None:
        if self._applying_mesh_preset:
            return
        self.mesh_preset_combo.blockSignals(True)
        self.mesh_preset_combo.setCurrentText(MESH_PRESET_CUSTOM)
        self.mesh_preset_combo.blockSignals(False)
        self.mesh_advanced_section.set_expanded(True)

    def _on_use_target_y_plus_toggled(self, checked: bool) -> None:
        self.target_y_plus_spin.setEnabled(checked)
        self.final_layer_thickness_spin.setEnabled(not checked)

    def _on_preview_mesh(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        if self.panel_mesh is None:
            self.geometry_status_label.setText("Load a 3D model before previewing the mesh.")
            return
        if self._mesh_preview_thread is not None and self._mesh_preview_thread.isRunning():
            return
        try:
            validate_domain_planes(self._ground_plane(), self._symmetry_planes())
        except ValueError as exc:
            self.geometry_status_label.setText(f"Invalid ground/symmetry plane configuration: {exc}")
            return
        self.preview_mesh_button.setEnabled(False)
        self.log_view.clear()
        self.geometry_status_label.setText("Building mesh for preview (blockMesh/snappyHexMesh)... see Log tab.")
        self.view_tabs.setCurrentWidget(self.log_tab)
        self._mesh_preview_thread = MeshPreviewWorker(
            self.panel_mesh, self._ground_plane(), self.mesh_settings(), self.execution_backend(),
            self._symmetry_planes(), self._preview_mach(), self.use_cache_checkbox.isChecked(), self,
        )
        self._mesh_preview_thread.log.connect(self._on_sweep_log)
        self._mesh_preview_thread.succeeded.connect(self._on_mesh_preview_succeeded)
        self._mesh_preview_thread.failed.connect(self._on_mesh_preview_failed)
        self._mesh_preview_thread.start()

    def _on_mesh_preview_succeeded(self, mesh_dir: Path) -> None:
        self.preview_mesh_button.setEnabled(True)
        surface = load_mesh_boundary_surface(mesh_dir)
        if surface is None:
            self.geometry_status_label.setText(f"Mesh built in {mesh_dir}, but a viewable preview isn't available for it.")
            return
        self.view_tabs.setCurrentIndex(0)
        self.plotter.clear_actors()
        self.plotter.add_mesh(surface, color="lightgray", show_edges=True, name="meshed_surface")
        self.plotter.reset_camera()
        self.geometry_status_label.setText(f"Mesh preview built in {mesh_dir}; edges show the real snappyHexMesh cells.")

    def _on_mesh_preview_failed(self, message: str) -> None:
        self.preview_mesh_button.setEnabled(True)
        self.geometry_status_label.setText(f"Mesh preview failed: {message}")

    def _build_solver_settings_box(self, parent: QWidget) -> QGroupBox:
        defaults = SolverSettings()
        box = QGroupBox("Solver settings", parent)
        solver_layout = QVBoxLayout(box)
        self.n_processors_spin = _int_spin(1, 128, defaults.n_processors, box)
        self.n_processors_spin.setToolTip(N_PROCESSORS_TOOLTIP)
        solver_layout.addLayout(labeled_row("Processors", self.n_processors_spin))
        self.use_cache_checkbox = QCheckBox("Reuse cached results for unchanged cases", box)
        self.use_cache_checkbox.setChecked(True)
        self.use_cache_checkbox.setToolTip(USE_CACHE_TOOLTIP)
        solver_layout.addWidget(self.use_cache_checkbox)

        solver_advanced = CollapsibleSection("Advanced solver parameters", box)
        solver_layout.addWidget(solver_advanced)
        solver_layout = solver_advanced

        self.turbulence_model_combo = NoScrollComboBox(box)
        self.turbulence_model_combo.addItems(list(TURBULENCE_MODELS))
        self.turbulence_model_combo.setCurrentText(defaults.turbulence_model)
        self.turbulence_model_combo.setToolTip(TURBULENCE_MODEL_TOOLTIP)
        self.turbulence_intensity_spin = NoScrollDoubleSpinBox(box)
        self.turbulence_intensity_spin.setDecimals(3)  # noqa: 34 (turbulence intensity is a fraction, e.g. 0.05)
        self.turbulence_intensity_spin.setRange(0.001, 0.5)
        self.turbulence_intensity_spin.setValue(defaults.turbulence_intensity)
        self.turbulence_intensity_spin.setToolTip(TURBULENCE_INTENSITY_TOOLTIP)
        self.max_iterations_spin = _int_spin(10, 100000, defaults.max_iterations, box)
        self.max_iterations_spin.setToolTip(MAX_ITERATIONS_TOOLTIP)
        self.residual_combo = NoScrollComboBox(box)
        self.residual_combo.addItems([f"{value:.0e}" for value in (1e-3, 1e-4, 1e-5, 1e-6)])
        self.residual_combo.setCurrentText(f"{defaults.convergence_residual:.0e}")
        self.residual_combo.setToolTip(RESIDUAL_TOOLTIP)
        self.mach_ceiling_spin = NoScrollDoubleSpinBox(box)
        self.mach_ceiling_spin.setRange(0.1, HARD_MACH_LIMIT)
        self.mach_ceiling_spin.setValue(defaults.mach_ceiling)
        self.mach_ceiling_spin.setToolTip(MACH_CEILING_TOOLTIP)

        solver_layout.addLayout(labeled_row("Turbulence model", self.turbulence_model_combo))
        solver_layout.addLayout(labeled_row("Turbulence intensity", self.turbulence_intensity_spin))
        solver_layout.addLayout(labeled_row("Max iterations", self.max_iterations_spin))
        solver_layout.addLayout(labeled_row("Convergence residual", self.residual_combo))
        solver_layout.addLayout(labeled_row("Mach ceiling", self.mach_ceiling_spin))
        return box

    def _build_execution_settings_box(self, parent: QWidget) -> QGroupBox:
        wsl_defaults = WslSettings()
        box = QGroupBox("Execution settings", parent)
        exec_layout = QVBoxLayout(box)

        self.execution_mode_combo = NoScrollComboBox(box)
        self.execution_mode_combo.addItems(list(EXECUTION_MODES))
        self.execution_mode_combo.setToolTip(EXECUTION_MODE_TOOLTIP)
        self.execution_mode_combo.currentTextChanged.connect(self._on_execution_mode_changed)
        exec_layout.addLayout(labeled_row("Run OpenFOAM via", self.execution_mode_combo))

        self.execution_stack = QStackedWidget(box)
        exec_layout.addWidget(self.execution_stack)

        wsl_page = QWidget(box)
        wsl_layout = QVBoxLayout(wsl_page)
        self.distro_combo = NoScrollComboBox(wsl_page)
        self.distro_combo.setEditable(True)
        distros = list_wsl_distros()
        self.distro_combo.addItems(distros)
        if wsl_defaults.distro:
            self.distro_combo.setCurrentText(wsl_defaults.distro)
        self.distro_combo.setToolTip(DISTRO_TOOLTIP)
        wsl_layout.addLayout(labeled_row("WSL distro (blank = default)", self.distro_combo))
        self.execution_stack.addWidget(wsl_page)

        native_page = QWidget(box)
        native_layout = QVBoxLayout(native_page)
        native_page_label = QLabel("Runs OpenFOAM commands directly on this Linux host.", native_page)
        native_page_label.setWordWrap(True)
        native_layout.addWidget(native_page_label)
        self.execution_stack.addWidget(native_page)

        self.bashrc_edit = QLineEdit(wsl_defaults.openfoam_bashrc, box)
        self.bashrc_edit.setPlaceholderText("(auto-detected at run time if left blank)")
        self.bashrc_edit.setToolTip(BASHRC_TOOLTIP)
        detect_bashrc_button = QPushButton("Auto-detect", box)
        detect_bashrc_button.setToolTip(AUTO_DETECT_BASHRC_TOOLTIP)
        detect_bashrc_button.clicked.connect(self._on_detect_bashrc)
        bashrc_row = QHBoxLayout()
        bashrc_row.addWidget(self.bashrc_edit, 1)
        bashrc_row.addWidget(detect_bashrc_button)
        self.case_root_edit = QLineEdit(str(wsl_defaults.case_root), box)
        self.case_root_edit.setToolTip(CASE_ROOT_TOOLTIP)
        case_root_button = QPushButton("Browse...", box)
        case_root_button.setToolTip(CASE_ROOT_BROWSE_TOOLTIP)
        case_root_button.clicked.connect(self._on_browse_case_root)
        case_root_row = QHBoxLayout()
        case_root_row.addWidget(self.case_root_edit, 1)
        case_root_row.addWidget(case_root_button)

        if distros:
            detected = find_openfoam_bashrc(wsl_defaults)
            if detected:
                self.bashrc_edit.setText(detected)

        exec_advanced = CollapsibleSection("OpenFOAM install path settings", box, expanded=not self.bashrc_edit.text().strip())
        exec_layout.addWidget(exec_advanced)
        exec_advanced.addWidget(QLabel("OpenFOAM etc/bashrc path", box))
        exec_advanced.addLayout(bashrc_row)
        exec_advanced.addWidget(QLabel("Case directory", box))
        exec_advanced.addLayout(case_root_row)
        return box

    def _on_execution_mode_changed(self, mode: str) -> None:
        self.execution_stack.setCurrentIndex(0 if mode == EXECUTION_WSL else 1)
        if mode == EXECUTION_NATIVE_LINUX and not self.bashrc_edit.text().strip():
            detected = find_openfoam_bashrc_native()
            if detected:
                self.bashrc_edit.setText(detected)

    def _build_view_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)

        self.view_tabs = QTabWidget(panel)
        tabs = self.view_tabs

        view_tab = QWidget(tabs)
        view_layout = QVBoxLayout(view_tab)
        view_controls = QHBoxLayout()
        view_controls.addWidget(QLabel("Case:", view_tab))
        self.case_combo = NoScrollComboBox(view_tab)
        self.case_combo.setToolTip(CASE_SELECT_TOOLTIP)
        self.case_combo.currentIndexChanged.connect(self._on_case_selection_changed)
        view_controls.addWidget(self.case_combo)
        view_controls.addWidget(QLabel("Color by:", view_tab))
        self.view_scalar_combo = NoScrollComboBox(view_tab)
        self.view_scalar_combo.addItems(
            [VIEW_MODE_GEOMETRY] + list(SURFACE_SCALAR_FIELDS.keys()) + [VIEW_MODE_VELOCITY_SLICE, VIEW_MODE_FLOW_TRACES]
        )
        self.view_scalar_combo.setToolTip(VIEW_SCALAR_TOOLTIP)
        self.view_scalar_combo.currentIndexChanged.connect(self._on_case_selection_changed)
        view_controls.addWidget(self.view_scalar_combo)
        view_controls.addStretch(1)
        view_layout.addLayout(view_controls)
        self.plotter = QtInteractor(view_tab)
        self.plotter.camera_position = [(0.0, -1.0, 0.0), (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0)]  # noqa: 21 (pyvista property setter, not our own attribute)
        view_layout.addWidget(self.plotter.interactor, stretch=1)
        tabs.addTab(view_tab, "3D view")

        self.log_tab = QWidget(tabs)
        log_layout = QVBoxLayout(self.log_tab)
        self.log_view = QPlainTextEdit(self.log_tab)
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        tabs.addTab(self.log_tab, "Log")

        plot_tab = QWidget(tabs)
        plot_layout = QVBoxLayout(plot_tab)
        plot_controls = QGridLayout()
        plot_controls.setColumnStretch(4, 1)
        self.plot_mode_combo = NoScrollComboBox(plot_tab)
        self.plot_mode_combo.addItems([PLOT_MODE_SWEEP, PLOT_MODE_CONVERGENCE, PLOT_MODE_RESIDUALS])
        self.plot_mode_combo.setToolTip(PLOT_MODE_TOOLTIP)
        self.plot_mode_combo.currentIndexChanged.connect(self._on_plot_mode_changed)
        plot_controls.addWidget(QLabel("Plot mode:", plot_tab), 0, 0)
        plot_controls.addWidget(self.plot_mode_combo, 0, 1)
        self.x_axis_combo = NoScrollComboBox(plot_tab)
        self.x_axis_combo.addItems(list(PLOT_X_QUANTITIES.keys()))
        self.x_axis_combo.setToolTip(PLOT_X_AXIS_TOOLTIP)
        self.x_axis_combo.currentIndexChanged.connect(self._replot)
        plot_controls.addWidget(QLabel("X axis:", plot_tab), 0, 2)
        plot_controls.addWidget(self.x_axis_combo, 0, 3)
        self.quantity_combo = NoScrollComboBox(plot_tab)
        self.quantity_combo.addItems(list(RESULT_QUANTITIES.keys()))
        self.quantity_combo.setToolTip(PLOT_QUANTITY_TOOLTIP)
        self.quantity_combo.currentIndexChanged.connect(self._replot)
        plot_controls.addWidget(QLabel("Plot quantity:", plot_tab), 1, 0)
        plot_controls.addWidget(self.quantity_combo, 1, 1)
        self.residual_field_combo = NoScrollComboBox(plot_tab)
        self.residual_field_combo.setToolTip(RESIDUAL_FIELD_TOOLTIP)
        self.residual_field_combo.currentIndexChanged.connect(self._replot)
        plot_controls.addWidget(QLabel("Residual field:", plot_tab), 1, 2)
        plot_controls.addWidget(self.residual_field_combo, 1, 3)
        plot_layout.addLayout(plot_controls)
        self.canvas = MplCanvas(plot_tab)
        plot_layout.addWidget(self.canvas, stretch=1)
        tabs.addTab(plot_tab, "Plot")
        self._on_plot_mode_changed()

        layout.addWidget(tabs, stretch=3)

        self.results_table = QTableWidget(0, len(RESULT_HEADERS), panel)
        self.results_table.setHorizontalHeaderLabels(RESULT_HEADERS)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.itemSelectionChanged.connect(self._on_results_table_selection_changed)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table, stretch=1)

        results_buttons = QHBoxLayout()
        self.export_csv_button = QPushButton("Export aerotable to CSV...", panel)
        self.export_csv_button.setToolTip(EXPORT_CSV_TOOLTIP)
        self.export_csv_button.clicked.connect(self._on_export_csv)
        results_buttons.addWidget(self.export_csv_button)
        self.import_results_button = QPushButton("Import results from directory...", panel)
        self.import_results_button.setToolTip(IMPORT_RESULTS_TOOLTIP)
        self.import_results_button.clicked.connect(self._on_import_results)
        results_buttons.addWidget(self.import_results_button)
        self.ansys_compare_button = QPushButton("Compare to ANSYS CSV...", panel)
        self.ansys_compare_button.setToolTip(ANSYS_IMPORT_TOOLTIP)
        self.ansys_compare_button.clicked.connect(self._on_compare_ansys)
        results_buttons.addWidget(self.ansys_compare_button)
        layout.addLayout(results_buttons)

        return panel

    def _on_mesh_changed(self) -> None:
        self.panel_mesh = self.geometry_panel.panel_mesh
        if self.panel_mesh is None:
            return

        if self.moment_ref_centroid_button.isChecked():
            self._apply_mesh_centroid_to_moment_ref()
        self._update_auto_reference_dims()

        self._refresh_viewport()
        self.plotter.reset_camera()

    def _apply_mesh_centroid_to_moment_ref(self) -> None:
        if self.panel_mesh is None:
            return
        center = self.panel_mesh.centroid()
        self.ref_x_spin.setValue(float(center[0]))
        self.ref_y_spin.setValue(float(center[1]))
        self.ref_z_spin.setValue(float(center[2]))

    def _on_moment_ref_centroid_toggled(self, checked: bool) -> None:
        self.ref_x_spin.setEnabled(not checked)
        self.ref_y_spin.setEnabled(not checked)
        self.ref_z_spin.setEnabled(not checked)
        if checked:
            self._apply_mesh_centroid_to_moment_ref()

    def _on_view_option_toggled(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        self._refresh_viewport()

    def _on_mach_input_toggled(self, checked: bool) -> None:
        self.rows["velocity"].setEnabled(not checked)
        self.rows["mach"].setEnabled(checked)
        self._refresh_viewport()

    def _on_ground_effect_toggled(self, checked: bool) -> None:
        self.ground_axis_combo.setEnabled(checked)
        self.ground_side_combo.setEnabled(checked)
        self._refresh_viewport()

    def _axis_index(self, axis: str) -> int:
        return {"X": 0, "Y": 1, "Z": 2}[axis]

    def _default_symmetry_offset(self, axis: str) -> float:
        if self.panel_mesh is None:
            return 0.0
        bounds = self.panel_mesh.bounds()
        index = self._axis_index(axis)
        return 0.5 * (bounds[2 * index] + bounds[2 * index + 1])

    def _on_symmetry_toggled(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        for checkbox, axis_combo, offset_spin in zip(
            self.symmetry_checkboxes, self.symmetry_axis_combos, self.symmetry_offset_spins
        ):
            enabled = checkbox.isChecked()
            newly_enabled = enabled and not axis_combo.isEnabled()
            axis_combo.setEnabled(enabled)
            offset_spin.setEnabled(enabled)
            if newly_enabled:
                offset_spin.setValue(self._default_symmetry_offset(axis_combo.currentText()))
        self._refresh_viewport()

    def _ground_plane(self) -> GroundPlane | None:
        if not self.ground_effect_checkbox.isChecked():
            return None
        return GroundPlane(axis=self.ground_axis_combo.currentText().lower(), side=self.ground_side_combo.currentText().lower())

    def _symmetry_planes(self) -> tuple[SymmetryPlane, ...]:
        planes = [
            SymmetryPlane(axis=axis_combo.currentText().lower(), offset=offset_spin.value())
            for checkbox, axis_combo, offset_spin in zip(
                self.symmetry_checkboxes, self.symmetry_axis_combos, self.symmetry_offset_spins
            )
            if checkbox.isChecked()
        ]
        return tuple(planes)

    def _refresh_viewport(self) -> None:
        if self.panel_mesh is None:
            return
        if self._reference_overlay_active():
            direction_unit = self._current_flow_direction_unit() if (self.show_flow_checkbox.isChecked() or self.show_wind_checkbox.isChecked()) else None
            self.show_reference_scene(direction_unit)
            return
        self._render_plain_mesh()

    def _render_plain_mesh(self) -> None:
        if self.panel_mesh is None:
            return
        self.plotter.clear_actors()
        self.plotter.add_mesh(panel_mesh_to_polydata(self.panel_mesh), color="lightgray", show_edges=False, name="panel_mesh")
        self._apply_extra_overlays()

    def _apply_extra_overlays(self) -> None:
        if self.panel_mesh is None:
            return
        if self.show_bbox_checkbox.isChecked():
            add_bounding_box(self.plotter, panel_mesh_to_polydata(self.panel_mesh))
        if self.show_domain_box_checkbox.isChecked():
            self._draw_domain_box()

    def _preview_mach(self) -> float:
        """Best-effort Mach estimate from the current (possibly swept) flow-condition
        fields, used only to preview the Mach-widened domain box; falls back to 0 (no
        widening shown) if the fields don't parse yet."""
        try:
            temperature_axis = self.rows["temperature"].axis()
        except ValueError:
            return 0.0
        temperature = float(temperature_axis.values[0]) if temperature_axis is not None else SEA_LEVEL_TEMPERATURE
        if self.mach_input_checkbox.isChecked():
            try:
                mach_axis = self.rows["mach"].axis()
            except ValueError:
                return 0.0
            return float(np.max(mach_axis.values)) if mach_axis is not None else 0.0
        try:
            velocity_axis = self.rows["velocity"].axis()
        except ValueError:
            return 0.0
        if velocity_axis is None:
            return 0.0
        velocity = float(np.max(velocity_axis.values))
        return FlowCondition(name="preview", velocity=velocity, alpha_deg=0.0, beta_deg=0.0, temperature=temperature).mach()

    def _draw_domain_box(self) -> None:
        if self.panel_mesh is None:
            return
        body_bounds = self.panel_mesh.bounds()
        mesh_settings = self.mesh_settings()
        ground_plane = self._ground_plane()
        symmetry_planes = self._symmetry_planes()
        try:
            domain = domain_bounds(body_bounds, mesh_settings, ground_plane, symmetry_planes, self._preview_mach())
        except ValueError as exc:
            self.domain_info_label.setText(f"Invalid ground/symmetry plane configuration: {exc}")
            return
        location = location_in_mesh(domain, body_bounds, mesh_settings)
        add_domain_box(self.plotter, domain, location, ground_plane, symmetry_planes)

        nx, ny, nz = background_cell_counts(domain, body_bounds, mesh_settings)
        size = (domain[1] - domain[0], domain[3] - domain[2], domain[5] - domain[4])
        self.domain_info_label.setText(
            f"Mesh domain (m): {size[0]:.3g} x {size[1]:.3g} x {size[2]:.3g}, background cells: {nx} x {ny} x {nz}"
        )

    def _on_apply_atmosphere(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        try:
            axis = self.altitude_row.axis()
        except ValueError:
            self.geometry_status_label.setText("Could not parse the altitude field; check the syntax tooltip.")
            return
        if axis is None:
            self.geometry_status_label.setText("Set an altitude value first.")
            return
        altitude = float(axis.values[0])
        state = us_standard_atmosphere(altitude)
        self.rows["density"].set_single_value(state.density)
        self.rows["temperature"].set_single_value(state.temperature)
        note = " (approximate above 86 km)" if state.approximate else ""
        self.geometry_status_label.setText(
            f"Applied ISA atmosphere at {altitude:.0f} m: T={state.temperature:.1f} K, rho={state.density:.3e} kg/m^3{note}"
        )

    def _on_browse_case_root(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        path = QFileDialog.getExistingDirectory(self, "Choose case directory", self.case_root_edit.text())
        if path:
            self.case_root_edit.setText(path)

    def _on_detect_bashrc(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        self.geometry_status_label.setText("Searching for an OpenFOAM installation...")
        detected = (
            find_openfoam_bashrc(self.wsl_settings_snapshot())
            if self.execution_mode_combo.currentText() == EXECUTION_WSL
            else find_openfoam_bashrc_native()
        )
        if detected is None:
            self.geometry_status_label.setText("No OpenFOAM installation found; enter the bashrc path manually.")
            return
        self.bashrc_edit.setText(detected)
        self.geometry_status_label.setText(f"Found OpenFOAM bashrc: {detected}")

    def mesh_settings(self) -> MeshSettings:
        return MeshSettings(
            upstream_lengths=self.upstream_spin.value(),
            downstream_lengths=self.downstream_spin.value(),
            side_lengths=self.side_spin.value(),
            top_lengths=self.top_spin.value(),
            background_cell_count=int(self.background_cell_count_spin.value()),
            surface_refinement_min=int(self.refine_min_spin.value()),
            surface_refinement_max=int(self.refine_max_spin.value()),
            n_boundary_layers=int(self.boundary_layers_spin.value()),
            boundary_layer_expansion_ratio=self.layer_expansion_spin.value(),
            final_layer_thickness_ratio=self.final_layer_thickness_spin.value(),
            use_target_y_plus=self.use_target_y_plus_checkbox.isChecked(),
            target_y_plus=self.target_y_plus_spin.value(),
            max_non_orthogonality=self.max_non_ortho_spin.value(),
            max_skewness=self.max_skewness_spin.value(),
            require_mesh_quality_pass=self.mesh_quality_gate_checkbox.isChecked(),
        )

    def solver_settings(self) -> SolverSettings:
        return SolverSettings(
            turbulence_model=self.turbulence_model_combo.currentText(),
            turbulence_intensity=self.turbulence_intensity_spin.value(),
            max_iterations=int(self.max_iterations_spin.value()),
            convergence_residual=float(self.residual_combo.currentText()),
            n_processors=int(self.n_processors_spin.value()),
            mach_ceiling=self.mach_ceiling_spin.value(),
        )

    def wsl_settings_snapshot(self) -> WslSettings:
        return WslSettings(
            distro=self.distro_combo.currentText().strip(),
            openfoam_bashrc=self.bashrc_edit.text().strip(),
            case_root=Path(self.case_root_edit.text().strip()),
        )

    def _native_settings(self) -> NativeLinuxSettings:
        return NativeLinuxSettings(
            openfoam_bashrc=self.bashrc_edit.text().strip(), case_root=Path(self.case_root_edit.text().strip())
        )

    def execution_backend(self) -> ExecutionBackend:
        if self.execution_mode_combo.currentText() == EXECUTION_WSL:
            return WslExecutionBackend(self.wsl_settings_snapshot())
        return NativeLinuxExecutionBackend(self._native_settings())

    def _on_run(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        if self.panel_mesh is None:
            self.geometry_status_label.setText("Load a 3D model before running.")
            return
        if self._sweep_thread is not None and self._sweep_thread.isRunning():
            return

        try:
            validate_domain_planes(self._ground_plane(), self._symmetry_planes())
        except ValueError as exc:
            self.geometry_status_label.setText(f"Invalid ground/symmetry plane configuration: {exc}")
            return

        velocity_key = "mach" if self.mach_input_checkbox.isChecked() else "velocity"
        axis_keys = [velocity_key if key == "velocity" else key for key in FLOW_AXIS_KEYS]
        try:
            axes = [axis for key in axis_keys if (axis := self.rows[key].axis()) is not None]
        except ValueError:
            self.geometry_status_label.setText("Could not parse a flow-condition field; check the syntax tooltip.")
            return

        swept = [axis for axis in axes if len(axis.values) > 1]
        if len(swept) > MAX_SWEPT_VARIABLES:
            self.geometry_status_label.setText(f"At most {MAX_SWEPT_VARIABLES} variables can be swept at once.")
            return

        base = FlowCondition(
            name="base", velocity=0.0, alpha_deg=0.0, beta_deg=0.0,
            wind_speed=self.wind_speed_spin.value(), wind_direction_deg=self.wind_direction_spin.value(),
            wind_elevation_deg=self.wind_elevation_spin.value(),
        )
        conditions = build_conditions(base, axes)

        self.run_button.setEnabled(False)
        self.log_view.clear()
        self.sweep_progress.setRange(0, len(conditions))
        self.sweep_progress.setValue(0)
        self.geometry_status_label.setText(f"Running {len(conditions)} case(s)... see Log tab for live progress.")
        self.view_tabs.setCurrentWidget(self.log_tab)
        reference_area, reference_length = self._reference_overrides()

        self.case_results = []
        self._live_case_log = None
        self._sweep_thread = OpenFoamSweepWorker(
            self.panel_mesh,
            conditions,
            self._moment_reference(),
            self._ground_plane(),
            self.mesh_settings(),
            self.solver_settings(),
            self.execution_backend(),
            reference_area,
            reference_length,
            self.geometry_panel.model_name,
            self._symmetry_planes(),
            self.use_cache_checkbox.isChecked(),
            self,
        )
        self._sweep_thread.log.connect(self._on_sweep_log)
        self._sweep_thread.progress.connect(self._on_sweep_progress)
        self._sweep_thread.case_finished.connect(self._on_sweep_case_finished)
        self._sweep_thread.case_started.connect(self._on_sweep_case_started)
        self._sweep_thread.succeeded.connect(self._on_sweep_succeeded)
        self._sweep_thread.failed.connect(self._on_sweep_failed)
        self._sweep_thread.start()

    def _on_sweep_case_started(self, label: str, run_dir: Path, application: str) -> None:
        self._live_case_log = run_dir / solve_log_filename(application)
        if self.plot_mode_combo.currentText() == PLOT_MODE_RESIDUALS:
            self._residual_timer.start()

    def _on_residual_timer_tick(self) -> None:
        if self.plot_mode_combo.currentText() != PLOT_MODE_RESIDUALS or self._live_case_log is None:
            self._residual_timer.stop()
            return
        self._update_residual_field_choices()
        self._replot()

    def _on_sweep_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        if line.startswith("Meshing ("):
            self.geometry_status_label.setText("Meshing (blockMesh/surfaceFeatures/snappyHexMesh)... see Log tab for live output.")
        elif line.endswith("..."):
            label = line.split("]")[0].lstrip("[") if "]" in line else ""
            if label:
                self.geometry_status_label.setText(f"Case '{label}': {line.split(']')[-1].strip()}... see Log tab.")

    def _on_sweep_progress(self, done: int, total: int) -> None:
        self.sweep_progress.setValue(done)
        self.geometry_status_label.setText(f"Ran case {done}/{total}... see Log tab for live progress.")

    def _on_sweep_case_finished(self, result: OpenFoamCaseResult) -> None:
        self._on_case_results_updated(self.case_results + [result])

    def _on_sweep_succeeded(self, results: list[OpenFoamCaseResult]) -> None:
        self.run_button.setEnabled(True)
        self.sweep_progress.setValue(self.sweep_progress.maximum())
        self.geometry_status_label.setText(f"Ran {len(results)} case(s).")
        self._residual_timer.stop()
        self._live_case_log = None
        self._on_case_results_updated(results)

    def _export_case_results_csv(self, path: str, case_results: list[OpenFoamCaseResult]) -> None:
        export_case_results_csv(path, case_results)

    def _on_compare_ansys(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        if not self.case_results:
            self.geometry_status_label.setText("No OpenFOAM results to compare yet -- run or import a case first.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load ANSYS results CSV", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            ansys_rows = parse_ansys_csv(path)
        except (ValueError, OSError) as exc:
            self.geometry_status_label.setText(f"Could not read ANSYS CSV: {exc}")
            return
        comparisons = compare_to_openfoam(ansys_rows, self.case_results)
        if not comparisons:
            self.geometry_status_label.setText("No matching (mach, alpha) cases found between the ANSYS CSV and the results table.")
            return
        lines = [
            f"M={c.mach:.3g} a={c.alpha_deg:.3g}: {c.quantity} ANSYS={c.ansys_value:.4g} OpenFOAM={c.openfoam_value:.4g} "
            f"({c.delta_pct:+.1f}%)"
            for c in comparisons
        ]
        self.log_view.appendPlainText("ANSYS comparison:\n" + "\n".join(lines))
        self.view_tabs.setCurrentWidget(self.log_tab)
        self.geometry_status_label.setText(f"Compared {len(comparisons)} value(s) against ANSYS; see Log tab.")

    def _on_import_results(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        if self._import_thread is not None and self._import_thread.isRunning():
            return
        directory = QFileDialog.getExistingDirectory(self, "Import OpenFOAM results", self.case_root_edit.text().strip())
        if not directory:
            return
        self._import_directory = directory
        self.import_results_button.setEnabled(False)
        self.geometry_status_label.setText(f"Searching {directory} for OpenFOAM result files...")
        self._import_thread = ImportSearchWorker(Path(directory), self)
        self._import_thread.found.connect(self._on_import_search_found)
        self._import_thread.failed.connect(self._on_import_search_failed)
        self._import_thread.start()

    def _on_import_search_found(self, roots: list[Path]) -> None:
        self.import_results_button.setEnabled(True)
        directory = self._import_directory
        if not roots:
            self.geometry_status_label.setText(f"Import failed: no OpenFOAM run cases found under {directory}")
            return
        chosen_roots = roots if len(roots) == 1 else self._resolve_import_roots(roots)
        if chosen_roots is None:
            self.geometry_status_label.setText("Import cancelled.")
            return
        try:
            results = [case for root in chosen_roots for case in import_case_results(root)]
        except (FileNotFoundError, ValueError, OSError) as exc:
            self.geometry_status_label.setText(f"Import failed: {exc}")
            return
        self.geometry_status_label.setText(f"Imported {len(results)} case(s) from {directory}.")
        self._on_case_results_updated(results)

    def _on_import_search_failed(self, message: str) -> None:
        self.import_results_button.setEnabled(True)
        self.geometry_status_label.setText(f"Import failed: {message}")

    def _resolve_import_roots(self, roots: list[Path]) -> list[Path] | None:
        box = QMessageBox(self)
        box.setWindowTitle("Multiple result sets found")
        box.setText(f"Found {len(roots)} OpenFOAM case directories. Import one, or all of them?")
        choose_button = box.addButton("Choose one...", QMessageBox.ButtonRole.ActionRole)
        all_button = box.addButton("Import all", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is all_button:
            return roots
        if clicked is choose_button:
            labels = [str(root) for root in roots]
            label, ok = QInputDialog.getItem(self, "Choose a case directory", "Case directory:", labels, editable=False)
            if not ok:
                return None
            return [roots[labels.index(label)]]
        return None

    def _on_case_results_updated(self, results: list[OpenFoamCaseResult]) -> None:
        previous_label = self.case_combo.currentText()
        self.case_results = results
        populate_case_table(self.results_table, self.case_results)
        labels = [case.condition.name or case.case_dir.name for case in self.case_results]
        self.case_combo.blockSignals(True)
        self.case_combo.clear()
        self.case_combo.addItems(labels)
        restore_index = labels.index(previous_label) if previous_label in labels else len(labels) - 1
        if restore_index >= 0:
            self.case_combo.setCurrentIndex(restore_index)
        self.case_combo.blockSignals(False)
        self.x_axis_combo.setCurrentText(self._default_x_axis_label(self.case_results))
        self._on_case_selection_changed()
        self._replot()

    def _on_results_table_selection_changed(self) -> None:
        row = self.results_table.currentRow()
        if row < 0 or row >= len(self.case_results):
            return
        self.case_combo.setCurrentIndex(row)
        if self.plot_mode_combo.currentText() != PLOT_MODE_CONVERGENCE:
            self.plot_mode_combo.setCurrentText(PLOT_MODE_CONVERGENCE)
        else:
            self._replot()

    def _default_x_axis_label(self, case_results: list[OpenFoamCaseResult]) -> str:
        if len(case_results) >= 2:
            for key in FLOW_AXIS_KEYS:
                label = FLOW_AXIS_LABELS[key]
                values = np.array([PLOT_X_QUANTITIES[label](case) for case in case_results])
                if not np.allclose(values, values[0]):
                    return label
        return next(iter(PLOT_X_QUANTITIES))

    def _on_plot_mode_changed(self, _index: int = 0) -> None:  # noqa: 21 (Qt slot signature)
        mode = self.plot_mode_combo.currentText()
        self.x_axis_combo.setEnabled(mode == PLOT_MODE_SWEEP)
        self.quantity_combo.setEnabled(mode != PLOT_MODE_RESIDUALS)
        self.residual_field_combo.setEnabled(mode == PLOT_MODE_RESIDUALS)
        if mode == PLOT_MODE_RESIDUALS:
            self._update_residual_field_choices()
            if self._sweep_thread is not None and self._sweep_thread.isRunning():
                self._residual_timer.start()
        else:
            self._residual_timer.stop()
        self._replot()

    def _on_case_selection_changed(self, _index: int = 0) -> None:  # noqa: 21 (Qt slot signature)
        view_mode = self.view_scalar_combo.currentText()
        if view_mode in (VIEW_MODE_VELOCITY_SLICE, VIEW_MODE_FLOW_TRACES) and self.case_results:
            self._render_case_volume_field(view_mode)
        elif view_mode != VIEW_MODE_GEOMETRY and self.case_results:
            self._render_case_surface_field()
        else:
            self._refresh_viewport()
        if self.plot_mode_combo.currentText() == PLOT_MODE_RESIDUALS:
            self._update_residual_field_choices()
        self._replot()

    def selected_case(self) -> OpenFoamCaseResult | None:
        index = self.case_combo.currentIndex()
        if not self.case_results or index < 0 or index >= len(self.case_results):
            return None
        return self.case_results[index]

    def _render_case_surface_field(self) -> None:
        case = self.selected_case()
        if case is None:
            self._refresh_viewport()
            return
        surface = load_case_surface(case.case_dir)
        if surface is None:
            self.geometry_status_label.setText(f"No sampled surface found for '{case.condition.name}'.")
            self._refresh_viewport()
            return
        field_label = self.view_scalar_combo.currentText()
        scalars = SURFACE_SCALAR_FIELDS[field_label](surface, case.condition)
        if scalars is None:
            self.geometry_status_label.setText(f"Sampled surface has no '{field_label}' data for this case.")
            self._refresh_viewport()
            return
        render_scalar_field(self.plotter, surface, scalars, field_label, zero_centered=field_label == "Pressure (Pa)")
        self.plotter.reset_camera()

    def _render_case_volume_field(self, view_mode: str) -> None:
        case = self.selected_case()
        if case is None:
            self._refresh_viewport()
            return
        volume = load_case_volume(case.case_dir)
        if volume is None:
            self.geometry_status_label.setText(f"No readable volumetric flow field found for '{case.condition.name}'.")
            self._refresh_viewport()
            return
        if view_mode == VIEW_MODE_VELOCITY_SLICE:
            sliced = velocity_magnitude_slice(volume)
            render_scalar_field(self.plotter, sliced, np.asarray(sliced[VELOCITY_MAGNITUDE_FIELD]), "Velocity magnitude (m/s)")
        else:
            self.plotter.clear_actors()
            bounds = volume.bounds
            source_center = (bounds[0], 0.5 * (bounds[2] + bounds[3]), 0.5 * (bounds[4] + bounds[5]))
            source_radius = 0.3 * max(bounds[3] - bounds[2], bounds[5] - bounds[4], 1e-9)
            traces = flow_path_traces(volume, source_center, source_radius)
            self.plotter.add_mesh(traces, color="cyan", line_width=2, name="flow_traces")
        if self.panel_mesh is not None:
            self.plotter.add_mesh(
                panel_mesh_to_polydata(self.panel_mesh), color="lightgray", opacity=0.3, show_edges=False, name="panel_mesh"
            )
        self.plotter.reset_camera()

    def _residuals_for_selected_case(self) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        case = self.selected_case()
        log_path = case.case_dir / solve_log_filename(case.application) if case is not None else self._live_case_log
        if log_path is None:
            return {}
        try:
            return parse_residual_history(log_path)
        except (FileNotFoundError, OSError):
            return {}

    def _update_residual_field_choices(self) -> None:
        current = self.residual_field_combo.currentText()
        fields = sorted(self._residuals_for_selected_case().keys())
        self.residual_field_combo.blockSignals(True)
        self.residual_field_combo.clear()
        self.residual_field_combo.addItems(fields)
        if current in fields:
            self.residual_field_combo.setCurrentText(current)
        self.residual_field_combo.blockSignals(False)

    def _replot(self, _index: int = 0) -> None:  # noqa: 21 (Qt slot signature)
        if not self.case_results:
            self.canvas.figure.clear()
            self.canvas.draw()
            return

        mode = self.plot_mode_combo.currentText()

        if mode == PLOT_MODE_RESIDUALS:
            field = self.residual_field_combo.currentText()
            residuals = self._residuals_for_selected_case()
            if not field or field not in residuals:
                self.canvas.figure.clear()
                self.canvas.draw()
                return
            iterations, values = residuals[field]
            draw_line_plot(self.canvas, iterations, values, "Iteration", f"Initial residual ({field})", yscale="log", annotate_extrema=False)
            return

        quantity_label = self.quantity_combo.currentText()
        quantity_fn = RESULT_QUANTITIES[quantity_label]

        if mode == PLOT_MODE_CONVERGENCE:
            case = self.selected_case()
            if case is None:
                self.canvas.figure.clear()
                self.canvas.draw()
                return
            try:
                time, snapshots = load_convergence_history(case)
            except (FileNotFoundError, ValueError, OSError) as exc:
                self.geometry_status_label.setText(f"Could not load convergence history: {exc}")
                return
            values = np.array([quantity_fn(snapshot) for snapshot in snapshots])
            draw_line_plot(self.canvas, time, values, "Iteration", quantity_label)
            return

        x_label = self.x_axis_combo.currentText()
        x_fn = PLOT_X_QUANTITIES[x_label]
        x_values = np.array([x_fn(case) for case in self.case_results])
        y_values = np.array([quantity_fn(case) for case in self.case_results])
        order = np.argsort(x_values)
        draw_line_plot(self.canvas, x_values[order], y_values[order], x_label, quantity_label)
