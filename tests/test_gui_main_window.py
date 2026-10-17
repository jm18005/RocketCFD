"""Automation panel wiring: mesh/solver settings round-trip, preset switching, progressive
disclosure of advanced sections, and basic run-guard behavior -- all offscreen, no
OpenFOAM install required."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import pyvista as pv
import trimesh

from rocketcfd.flow import FlowCondition
from rocketcfd.geometry import to_panel_mesh
from rocketcfd.gui import main_window as main_window_module
from rocketcfd.gui.main_window import MainWindow, MeshPreviewWorker, OpenFoamSweepWorker, VIEW_MODE_VELOCITY_SLICE
from rocketcfd.openfoam.case_result import OpenFoamCaseResult
from rocketcfd.openfoam.coefficients import Coefficients
from rocketcfd.openfoam.settings import (
    MESH_PRESET_COARSE,
    MESH_PRESET_CUSTOM,
    MeshSettings,
    SolverSettings,
    mesh_settings_for_preset,
)


@pytest.fixture
def window() -> MainWindow:  # noqa: 21 (pytest fixture, injected by name into the test functions below)
    return MainWindow()


def _give_mesh(window: MainWindow) -> None:
    sphere = trimesh.creation.icosphere(radius=0.5, subdivisions=1)
    window.panel_mesh = to_panel_mesh(sphere)


def test_mesh_settings_default_matches_dataclass_defaults(window: MainWindow) -> None:
    assert window.mesh_settings() == MeshSettings()


def test_solver_settings_default_matches_dataclass_defaults(window: MainWindow) -> None:
    assert window.solver_settings() == SolverSettings()


def test_mesh_advanced_section_starts_collapsed(window: MainWindow) -> None:
    assert window.mesh_advanced_section._body.isHidden() is True


def test_selecting_coarse_preset_updates_fields(window: MainWindow) -> None:
    window.mesh_preset_combo.setCurrentText(MESH_PRESET_COARSE)
    expected = mesh_settings_for_preset(MESH_PRESET_COARSE)
    settings = window.mesh_settings()
    assert settings.background_cell_count == expected.background_cell_count
    assert settings.surface_refinement_max == expected.surface_refinement_max
    assert settings.target_y_plus == pytest.approx(expected.target_y_plus)


def test_manually_editing_a_mesh_field_switches_preset_to_custom_and_expands_section(window: MainWindow) -> None:
    window.background_cell_count_spin.setValue(int(window.background_cell_count_spin.value()) + 5)
    assert window.mesh_preset_combo.currentText() == MESH_PRESET_CUSTOM
    assert window.mesh_advanced_section._body.isHidden() is False


def test_use_target_y_plus_toggle_swaps_enabled_fields(window: MainWindow) -> None:
    window.use_target_y_plus_checkbox.setChecked(True)
    assert window.target_y_plus_spin.isEnabled() is True
    assert window.final_layer_thickness_spin.isEnabled() is False
    window.use_target_y_plus_checkbox.setChecked(False)
    assert window.target_y_plus_spin.isEnabled() is False
    assert window.final_layer_thickness_spin.isEnabled() is True


def test_ref_dims_override_toggle_enables_override_fields(window: MainWindow) -> None:
    assert window.ref_area_spin.isEnabled() is False
    window.ref_dims_override_checkbox.setChecked(True)
    assert window.ref_area_spin.isEnabled() is True
    assert window.ref_length_spin.isEnabled() is True


def test_run_without_geometry_reports_status_and_does_not_start(window: MainWindow) -> None:
    window._on_run()
    assert "Load a 3D model" in window.geometry_status_label.text()
    assert window._sweep_thread is None


def test_run_rejects_more_than_max_swept_variables(window: MainWindow) -> None:
    _give_mesh(window)
    window.rows["velocity"].values_edit.setText("50, 100, 150")
    window.rows["alpha_deg"].values_edit.setText("0, 2, 4")
    window.rows["beta_deg"].values_edit.setText("0, 1, 2")
    window.rows["temperature"].values_edit.setText("280, 290, 300")
    window._on_run()
    assert "At most" in window.geometry_status_label.text()
    assert window._sweep_thread is None


def test_run_accepts_up_to_max_swept_variables(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(OpenFoamSweepWorker, "start", lambda self: None)
    _give_mesh(window)
    window.rows["velocity"].values_edit.setText("50, 100")
    window.rows["alpha_deg"].values_edit.setText("0, 2")
    window.rows["beta_deg"].values_edit.setText("0, 1")
    window._on_run()
    assert "At most" not in window.geometry_status_label.text()
    assert window._sweep_thread is not None


def test_apply_atmosphere_fills_density_and_temperature(window: MainWindow) -> None:
    window.altitude_row.values_edit.setText("0")
    window._on_apply_atmosphere()
    assert window.rows["density"].values_edit.text() != ""
    assert window.rows["temperature"].values_edit.text() != ""
    assert "Applied ISA atmosphere" in window.geometry_status_label.text()


def test_preview_mesh_without_geometry_reports_status(window: MainWindow) -> None:
    window._on_preview_mesh()
    assert "Load a 3D model" in window.geometry_status_label.text()
    assert window._mesh_preview_thread is None


def test_preview_mesh_starts_worker_with_geometry(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MeshPreviewWorker, "start", lambda self: None)
    _give_mesh(window)
    window._on_preview_mesh()
    assert window._mesh_preview_thread is not None
    assert "Building mesh for preview" in window.geometry_status_label.text()


def test_mesh_preview_succeeded_with_no_surface_reports_status(window: MainWindow, tmp_path: Path) -> None:
    window._on_mesh_preview_succeeded(tmp_path)
    assert "viewable preview isn't available" in window.geometry_status_label.text()


def test_mesh_preview_failed_reports_status(window: MainWindow) -> None:
    window._on_mesh_preview_failed("boom")
    assert "Mesh preview failed: boom" in window.geometry_status_label.text()


def _fake_case_result(case_dir: Path) -> OpenFoamCaseResult:
    return OpenFoamCaseResult(
        condition=FlowCondition(name="c", velocity=10.0, alpha_deg=0.0, beta_deg=0.0),
        coefficients=Coefficients(cd=0.0, cl=0.0, cs=0.0, cm=np.zeros(3)),
        reference_area=1.0, reference_length=1.0, force=np.zeros(3), moment=np.zeros(3),
        case_dir=case_dir, application="simpleFoam",
    )


def test_velocity_slice_without_volume_field_reports_status(window: MainWindow, tmp_path: Path) -> None:
    window._on_case_results_updated([_fake_case_result(tmp_path)])
    window.view_scalar_combo.setCurrentText(VIEW_MODE_VELOCITY_SLICE)
    assert "No readable volumetric flow field" in window.geometry_status_label.text()


def test_velocity_slice_renders_when_volume_available(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    grid = pv.ImageData(dimensions=(4, 4, 4), spacing=(1.0, 1.0, 1.0)).cast_to_unstructured_grid()
    grid.point_data["U"] = np.tile(np.array([3.0, 4.0, 0.0]), (grid.n_points, 1))
    grid.point_data["U_magnitude"] = np.full(grid.n_points, 5.0)
    monkeypatch.setattr(main_window_module, "load_case_volume", lambda _run_dir: grid)

    window._on_case_results_updated([_fake_case_result(tmp_path)])
    window.view_scalar_combo.setCurrentText(VIEW_MODE_VELOCITY_SLICE)

    assert "No readable volumetric flow field" not in window.geometry_status_label.text()


def test_mesh_changed_centers_moment_reference_on_geometry(window: MainWindow) -> None:
    sphere = trimesh.creation.icosphere(radius=0.5, subdivisions=1)
    window.geometry_panel.panel_mesh = to_panel_mesh(sphere)
    window._on_mesh_changed()
    assert window.ref_x_spin.value() == pytest.approx(window.panel_mesh.centroid()[0], abs=1e-6)
