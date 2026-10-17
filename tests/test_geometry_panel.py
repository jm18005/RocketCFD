"""GeometryPanel: rotation is applied to the panel mesh live (so both the 3D view and the
solve pipeline, which both read panel_mesh, pick it up), and the bounding-box readout
stays in sync with the current orientation/scale."""
from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from rocketcfd.gui.geometry_panel import GeometryPanel

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def panel() -> GeometryPanel:  # noqa: 21 (pytest fixture, injected by name into the test functions below)
    widget = GeometryPanel()
    widget._raw_mesh = trimesh.creation.box(extents=[4.0, 1.0, 2.0])
    widget._geometry_load_status = "test"
    widget._rebuild_scaled_mesh()
    return widget


def test_rotation_changes_panel_mesh_bounds_in_real_time(panel: GeometryPanel) -> None:
    original_bounds = panel.panel_mesh.bounds()
    events = []
    panel.mesh_changed.connect(lambda: events.append(1))

    panel.rotate_y_spin.setValue(90.0)

    assert len(events) == 1
    xmin, xmax, ymin, ymax, zmin, zmax = panel.panel_mesh.bounds()
    assert abs((zmax - zmin) - 4.0) < 1e-6
    assert abs((xmax - xmin) - 2.0) < 1e-6
    assert panel.panel_mesh.bounds() != original_bounds


def test_bbox_label_reports_length_width_height(panel: GeometryPanel) -> None:
    text = panel.bbox_label.text()
    assert "Length (X) 4" in text
    assert "Width (Y) 1" in text
    assert "Height (Z) 2" in text


def test_bbox_label_updates_after_rotation(panel: GeometryPanel) -> None:
    panel.rotate_y_spin.setValue(90.0)
    text = panel.bbox_label.text()
    assert "Length (X) 2" in text
    assert "Height (Z) 4" in text


def test_loading_a_new_model_resets_rotation(panel: GeometryPanel) -> None:
    panel.rotate_x_spin.setValue(45.0)
    panel.load_model(str(EXAMPLES_DIR / "sphere.stl"))
    assert panel.rotate_x_spin.value() == 0.0
    assert panel.rotate_y_spin.value() == 0.0
    assert panel.rotate_z_spin.value() == 0.0
