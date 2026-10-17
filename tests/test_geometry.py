"""Geometry loading, watertight repair/failure, and frontal-area computation."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from rocketcfd import geometry
from rocketcfd.geometry import (
    CAD_INSTALL_HINT,
    GeometryNotWatertightError,
    ensure_watertight,
    frontal_area,
    load_model,
    rotate_mesh,
    to_panel_mesh,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_load_watertight_sphere_stays_watertight() -> None:
    mesh = load_model(EXAMPLES_DIR / "sphere.stl")
    repaired, report = ensure_watertight(mesh)
    assert report.was_watertight
    assert report.is_watertight
    assert repaired.is_watertight


def test_load_model_rejects_unsupported_extension(tmp_path: Path) -> None:
    bogus = tmp_path / "model.xyz"
    bogus.write_text("not a model")
    with pytest.raises(ValueError, match="Unsupported 3D model format"):
        load_model(bogus)


def test_load_model_step_without_cad_backend_raises_install_hint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(geometry, "brep_backend_available", lambda: False)
    fake_step = tmp_path / "rocket.step"
    fake_step.write_text("not real STEP data")
    with pytest.raises(RuntimeError) as exc_info:
        load_model(fake_step)
    assert str(exc_info.value) == CAD_INSTALL_HINT


def test_ensure_watertight_repairs_a_hole() -> None:
    box = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    faces_with_hole = box.faces[:-1]
    holey = trimesh.Trimesh(vertices=box.vertices, faces=faces_with_hole, process=False)
    assert not holey.is_watertight
    repaired, report = ensure_watertight(holey)
    assert not report.was_watertight
    assert report.is_watertight
    assert repaired.is_watertight


def test_ensure_watertight_raises_when_unrepairable() -> None:
    vertices = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    faces = np.array([[0, 1, 2]])
    sliver = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    with pytest.raises(GeometryNotWatertightError):
        ensure_watertight(sliver)


def test_rotate_mesh_about_y_swaps_x_and_z_extents() -> None:
    box = trimesh.creation.box(extents=[4.0, 1.0, 2.0])
    rotated = rotate_mesh(box, (0.0, 90.0, 0.0))
    panel_mesh = to_panel_mesh(rotated)
    xmin, xmax, ymin, ymax, zmin, zmax = panel_mesh.bounds()
    assert abs((zmax - zmin) - 4.0) < 1e-6
    assert abs((ymax - ymin) - 1.0) < 1e-6
    assert abs((xmax - xmin) - 2.0) < 1e-6


def test_rotate_mesh_preserves_volume() -> None:
    box = trimesh.creation.box(extents=[3.0, 2.0, 1.0])
    rotated = rotate_mesh(box, (12.0, 34.0, 56.0))
    assert abs(rotated.volume - box.volume) / box.volume < 1e-9


def test_rotate_mesh_zero_angles_is_identity() -> None:
    box = trimesh.creation.box(extents=[3.0, 2.0, 1.0])
    rotated = rotate_mesh(box, (0.0, 0.0, 0.0))
    assert np.allclose(rotated.vertices, box.vertices)


def test_frontal_area_of_sphere_matches_analytic_disk() -> None:
    mesh = load_model(EXAMPLES_DIR / "sphere.stl")
    repaired, _ = ensure_watertight(mesh)
    panel_mesh = to_panel_mesh(repaired)
    radius = float(np.max(panel_mesh.vertices[:, 0]) - panel_mesh.centroid()[0])
    area = frontal_area(panel_mesh, np.array([1.0, 0.0, 0.0]))
    expected = np.pi * radius**2
    assert abs(area - expected) / expected < 0.05
