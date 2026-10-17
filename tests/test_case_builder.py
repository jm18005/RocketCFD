"""Case-directory generation: right files for the right solver regime, without needing
an OpenFOAM install to run them."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from rocketcfd.flow import FlowCondition
from rocketcfd.geometry import rotate_mesh, to_panel_mesh
from rocketcfd.openfoam.case_builder import write_mesh_case, write_run_case
from rocketcfd.openfoam.settings import MeshSettings, SolverSettings, SymmetryPlane
from rocketcfd.templates_geometry import assemble_rocket_labeled, body_tube, nosecone


def _mesh_dir(tmp_path: Path) -> Path:
    sphere = trimesh.creation.icosphere(radius=0.5, subdivisions=2)
    panel_mesh = to_panel_mesh(sphere)
    mesh_dir = tmp_path / "mesh"
    write_mesh_case(mesh_dir, panel_mesh, MeshSettings(), ground_plane=None)
    (mesh_dir / "constant" / "polyMesh").mkdir(parents=True, exist_ok=True)
    return mesh_dir


def test_write_mesh_case_bakes_rotation_into_the_solved_body_stl(tmp_path: Path) -> None:
    box = trimesh.creation.box(extents=[4.0, 1.0, 2.0])
    rotated = rotate_mesh(box, (0.0, 90.0, 0.0))
    panel_mesh = to_panel_mesh(rotated)
    mesh_dir = tmp_path / "mesh"
    write_mesh_case(mesh_dir, panel_mesh, MeshSettings(), ground_plane=None)

    written = trimesh.load(str(mesh_dir / "constant" / "triSurface" / "body.stl"), force="mesh")
    xmin, xmax, ymin, ymax, zmin, zmax = written.bounds[0][0], written.bounds[1][0], written.bounds[0][1], written.bounds[1][1], written.bounds[0][2], written.bounds[1][2]
    assert abs((xmax - xmin) - 2.0) < 1e-6
    assert abs((zmax - zmin) - 4.0) < 1e-6


def test_incompressible_case_writes_kinematic_pressure_and_no_thermo(tmp_path: Path) -> None:
    mesh_dir = _mesh_dir(tmp_path)
    run_dir = tmp_path / "run_incompressible"
    condition = FlowCondition(name="low_mach", velocity=30.0, alpha_deg=0.0, beta_deg=0.0)
    selection = write_run_case(run_dir, mesh_dir, condition, SolverSettings(), np.zeros(3), None, 1.0)
    assert selection.application == "simpleFoam"
    assert (run_dir / "constant" / "transportProperties").exists()
    assert not (run_dir / "constant" / "thermophysicalProperties").exists()
    assert not (run_dir / "0" / "T").exists()


def test_supersonic_case_writes_compressible_fields(tmp_path: Path) -> None:
    mesh_dir = _mesh_dir(tmp_path)
    run_dir = tmp_path / "run_supersonic"
    condition = FlowCondition(name="supersonic", velocity=700.0, alpha_deg=2.0, beta_deg=0.0)
    selection = write_run_case(run_dir, mesh_dir, condition, SolverSettings(), np.zeros(3), None, 1.0)
    assert selection.application == "rhoCentralFoam"
    assert (run_dir / "constant" / "thermophysicalProperties").exists()
    assert (run_dir / "0" / "T").exists()
    assert (run_dir / "0" / "p").read_text().count("dimensions [1 -1 -2 0 0 0 0]") == 1


def test_symmetry_plane_propagates_to_field_files(tmp_path: Path) -> None:
    mesh_dir = _mesh_dir(tmp_path)
    run_dir = tmp_path / "run_symmetry"
    condition = FlowCondition(name="sym", velocity=30.0, alpha_deg=0.0, beta_deg=0.0)
    write_run_case(run_dir, mesh_dir, condition, SolverSettings(), np.zeros(3), None, 1.0, symmetry_planes=(SymmetryPlane("y", 0.0),))
    assert "symmetryPlane" in (run_dir / "0" / "U").read_text()


def test_write_mesh_case_widens_domain_for_supersonic_mach(tmp_path: Path) -> None:
    sphere = trimesh.creation.icosphere(radius=0.5, subdivisions=2)
    panel_mesh = to_panel_mesh(sphere)
    subsonic_dir, supersonic_dir = tmp_path / "mesh_subsonic", tmp_path / "mesh_supersonic"
    write_mesh_case(subsonic_dir, panel_mesh, MeshSettings(), ground_plane=None, mach=0.3)
    write_mesh_case(supersonic_dir, panel_mesh, MeshSettings(), ground_plane=None, mach=3.0)
    subsonic_text = (subsonic_dir / "system" / "blockMeshDict").read_text()
    supersonic_text = (supersonic_dir / "system" / "blockMeshDict").read_text()
    assert subsonic_text != supersonic_text


def test_write_mesh_case_sizes_layer_from_target_y_plus_reference_condition(tmp_path: Path) -> None:
    sphere = trimesh.creation.icosphere(radius=0.5, subdivisions=2)
    panel_mesh = to_panel_mesh(sphere)
    mesh_dir = tmp_path / "mesh"
    reference_condition = FlowCondition(name="fast", velocity=200.0, alpha_deg=0.0, beta_deg=0.0)
    write_mesh_case(
        mesh_dir, panel_mesh, MeshSettings(use_target_y_plus=True, target_y_plus=1.0), ground_plane=None,
        reference_condition=reference_condition,
    )
    snappy_text = (mesh_dir / "system" / "snappyHexMeshDict").read_text()
    assert "relativeSizes false;" in snappy_text
    assert "firstLayerThickness" in snappy_text


def test_write_mesh_case_without_target_y_plus_uses_relative_layer_sizing(tmp_path: Path) -> None:
    sphere = trimesh.creation.icosphere(radius=0.5, subdivisions=2)
    panel_mesh = to_panel_mesh(sphere)
    mesh_dir = tmp_path / "mesh"
    write_mesh_case(mesh_dir, panel_mesh, MeshSettings(use_target_y_plus=False), ground_plane=None)
    snappy_text = (mesh_dir / "system" / "snappyHexMeshDict").read_text()
    assert "relativeSizes true;" in snappy_text


def test_write_mesh_case_writes_multi_region_stl_from_labeled_geometry(tmp_path: Path) -> None:
    nose = nosecone(length=0.5, base_diameter=0.2)
    body = body_tube(length=1.0, diameter=0.2)
    labeled_mesh, face_regions = assemble_rocket_labeled(nose, body)
    panel_mesh = to_panel_mesh(labeled_mesh, face_regions=face_regions)
    mesh_dir = tmp_path / "mesh"
    write_mesh_case(mesh_dir, panel_mesh, MeshSettings(), ground_plane=None)
    stl_text = (mesh_dir / "constant" / "triSurface" / "body.stl").read_text()
    assert "solid nosecone" in stl_text
    assert "solid body_tube" in stl_text


def test_write_mesh_case_applies_feature_refinement_levels(tmp_path: Path) -> None:
    nose = nosecone(length=0.5, base_diameter=0.2)
    body = body_tube(length=1.0, diameter=0.2)
    labeled_mesh, face_regions = assemble_rocket_labeled(nose, body)
    panel_mesh = to_panel_mesh(labeled_mesh, face_regions=face_regions)
    mesh_dir = tmp_path / "mesh"
    mesh_settings = MeshSettings(feature_refinement_levels={"nosecone": (5, 6)})
    write_mesh_case(mesh_dir, panel_mesh, mesh_settings, ground_plane=None)
    snappy_text = (mesh_dir / "system" / "snappyHexMeshDict").read_text()
    assert "nosecone { level (5 6); }" in snappy_text
