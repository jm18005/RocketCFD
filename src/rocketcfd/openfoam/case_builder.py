"""Writes OpenFOAM case directories (mesh case + per-condition run case) to disk."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import trimesh

from rocketcfd.flow import FlowCondition
from rocketcfd.gas import sutherland_viscosity
from rocketcfd.gas import static_pressure as compute_static_pressure
from rocketcfd.geometry import PanelMesh
from rocketcfd.openfoam import templates
from rocketcfd.openfoam.boundary_layer import first_layer_thickness as compute_first_layer_thickness
from rocketcfd.openfoam.settings import GroundPlane, MeshSettings, SolverSettings, SymmetryPlane
from rocketcfd.solver_selection import INCOMPRESSIBLE, SUPERSONIC, SolverSelection, select_solver

CMU = 0.09
MIXING_LENGTH_FRACTION = 0.07
NU_TILDA_TO_NU = 3.0


def _body_bounds(panel_mesh: PanelMesh) -> tuple[float, float, float, float, float, float]:
    return panel_mesh.bounds()


def _write_body_stl(mesh_dir: Path, panel_mesh: PanelMesh) -> None:
    """A plain STL (single "solid body") unless panel_mesh.face_regions is set, in which
    case each named region becomes its own "solid <name>" block: snappyHexMesh splits a
    multi-solid triSurfaceMesh into per-region patches, which
    templates.snappy_hex_mesh_dict's feature_refinement argument then targets by name."""
    path = mesh_dir / "constant" / "triSurface" / "body.stl"
    if panel_mesh.face_regions is None:
        body = trimesh.Trimesh(vertices=panel_mesh.vertices, faces=panel_mesh.faces, process=False)
        body.export(str(path))
        return

    lines: list[str] = []
    for region in dict.fromkeys(panel_mesh.face_regions):
        lines.append(f"solid {region}")
        for face in panel_mesh.faces[panel_mesh.face_regions == region]:
            v0, v1, v2 = panel_mesh.vertices[face]
            normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(normal)
            if norm > 1e-12:
                normal = normal / norm
            lines.append(f"  facet normal {normal[0]:.9g} {normal[1]:.9g} {normal[2]:.9g}")
            lines.append("    outer loop")
            for vertex in (v0, v1, v2):
                lines.append(f"      vertex {vertex[0]:.9g} {vertex[1]:.9g} {vertex[2]:.9g}")
            lines.append("    endloop")
            lines.append("  endfacet")
        lines.append(f"endsolid {region}")
    path.write_text("\n".join(lines) + "\n")


def write_mesh_case(
    mesh_dir: Path,
    panel_mesh: PanelMesh,
    mesh_settings: MeshSettings,
    ground_plane: GroundPlane | None = None,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
    mach: float = 0.0,
    reference_condition: FlowCondition | None = None,
) -> None:
    """mach is the highest Mach number reached across the sweep this mesh serves (widens
    the downstream domain for supersonic runs). reference_condition, when given and
    mesh_settings.use_target_y_plus, sizes the first boundary-layer cell to
    mesh_settings.target_y_plus for that condition (see openfoam.boundary_layer); the
    mesh is still built once and shared across the whole sweep, so this uses one
    representative condition rather than a per-condition layer size."""
    (mesh_dir / "constant" / "triSurface").mkdir(parents=True, exist_ok=True)
    (mesh_dir / "system").mkdir(parents=True, exist_ok=True)

    _write_body_stl(mesh_dir, panel_mesh)

    bounds = _body_bounds(panel_mesh)
    domain = templates.domain_bounds(bounds, mesh_settings, ground_plane, symmetry_planes, mach)
    cell_counts = templates.background_cell_counts(domain, bounds, mesh_settings)
    location = templates.location_in_mesh(domain, bounds, mesh_settings)

    layer_thickness = None
    if mesh_settings.use_target_y_plus and reference_condition is not None and reference_condition.velocity > 0.0:
        reference_length = max(bounds[1] - bounds[0], 1e-9)
        viscosity = sutherland_viscosity(reference_condition.temperature)
        layer_thickness = compute_first_layer_thickness(
            mesh_settings.target_y_plus, reference_condition.velocity, reference_condition.density, viscosity, reference_length,
        )

    (mesh_dir / "system" / "controlDict").write_text(templates.control_dict("simpleFoam", 1, 1))
    (mesh_dir / "system" / "blockMeshDict").write_text(
        templates.block_mesh_dict(domain, cell_counts, ground_plane, symmetry_planes)
    )
    (mesh_dir / "system" / "surfaceFeaturesDict").write_text(templates.surface_features_dict())
    (mesh_dir / "system" / "snappyHexMeshDict").write_text(
        templates.snappy_hex_mesh_dict(
            mesh_settings, location, layer_thickness, mesh_settings.feature_refinement_levels,
        )
    )
    (mesh_dir / "system" / "fvSchemes").write_text(templates.fv_schemes_incompressible())
    (mesh_dir / "system" / "fvSolution").write_text(templates.fv_solution_incompressible(1e-4))


def _turbulence_initial_values(
    condition: FlowCondition, solver_settings: SolverSettings, kinematic_viscosity: float, reference_length: float
) -> tuple[float, float, float]:
    intensity = solver_settings.turbulence_intensity
    k0 = 1.5 * (intensity * condition.velocity) ** 2
    mixing_length = max(MIXING_LENGTH_FRACTION * reference_length, 1e-6)
    omega0 = np.sqrt(max(k0, 1e-12)) / (CMU**0.25 * mixing_length)
    nu_tilda0 = NU_TILDA_TO_NU * kinematic_viscosity
    return k0, omega0, nu_tilda0


def _write_turbulence_fields(
    run_dir: Path, solver_settings: SolverSettings, wall_patches: list[str], k0: float, omega0: float, nu_tilda0: float,
    symmetry_planes: tuple[SymmetryPlane, ...],
) -> None:
    if solver_settings.turbulence_model == "kOmegaSST":
        (run_dir / "0" / "k").write_text(templates.k_field(k0, wall_patches, symmetry_planes))
        (run_dir / "0" / "omega").write_text(templates.omega_field(omega0, wall_patches, symmetry_planes))
        (run_dir / "0" / "nut").write_text(templates.nut_field_komega(wall_patches, symmetry_planes))
    else:
        (run_dir / "0" / "nuTilda").write_text(templates.nu_tilda_field(nu_tilda0, wall_patches, symmetry_planes))
        (run_dir / "0" / "nut").write_text(templates.nut_field_sa(wall_patches, symmetry_planes))


def write_run_case(
    run_dir: Path,
    mesh_dir: Path,
    condition: FlowCondition,
    solver_settings: SolverSettings,
    moment_ref: np.ndarray,
    ground_plane: GroundPlane | None,
    reference_length: float,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
) -> SolverSelection:
    """Writes 0/, constant/, system/ for one flow condition, picking the OpenFOAM solver
    from the condition's Mach number and solver_settings.mach_ceiling. Returns the
    SolverSelection actually used, so callers can surface its warnings."""
    (run_dir / "0").mkdir(parents=True, exist_ok=True)
    (run_dir / "constant").mkdir(parents=True, exist_ok=True)
    (run_dir / "system").mkdir(parents=True, exist_ok=True)

    shutil.copytree(mesh_dir / "constant" / "polyMesh", run_dir / "constant" / "polyMesh", dirs_exist_ok=True)
    shutil.copytree(mesh_dir / "constant" / "triSurface", run_dir / "constant" / "triSurface", dirs_exist_ok=True)

    selection = select_solver(condition.mach(), solver_settings.mach_ceiling)

    wall_patches = ["body"] + (["ground"] if ground_plane is not None else [])
    velocity = condition.velocity * condition.direction_unit()
    viscosity = sutherland_viscosity(condition.temperature)
    kinematic_viscosity = viscosity / condition.density
    k0, omega0, nu_tilda0 = _turbulence_initial_values(condition, solver_settings, kinematic_viscosity, reference_length)

    (run_dir / "constant" / "turbulenceProperties").write_text(
        templates.turbulence_properties(solver_settings.turbulence_model)
    )

    write_interval = max(solver_settings.max_iterations // 5, 1)

    if selection.regime == INCOMPRESSIBLE:
        (run_dir / "constant" / "transportProperties").write_text(templates.transport_properties(kinematic_viscosity))
        (run_dir / "system" / "controlDict").write_text(
            templates.control_dict(
                selection.application, solver_settings.max_iterations, write_interval,
                forces_patches=wall_patches, rho_inf=condition.density, cofr=moment_ref, compressible=False,
            )
        )
        (run_dir / "system" / "fvSchemes").write_text(templates.fv_schemes_incompressible())
        (run_dir / "system" / "fvSolution").write_text(
            templates.fv_solution_incompressible(solver_settings.convergence_residual)
        )
        (run_dir / "0" / "U").write_text(templates.u_field(velocity, wall_patches, symmetry_planes))
        (run_dir / "0" / "p").write_text(templates.p_field(wall_patches, symmetry_planes))
    else:
        (run_dir / "constant" / "thermophysicalProperties").write_text(templates.thermophysical_properties())
        pressure = compute_static_pressure(condition.density, condition.temperature)
        if selection.regime == SUPERSONIC:
            (run_dir / "system" / "controlDict").write_text(
                templates.control_dict(
                    selection.application, solver_settings.max_iterations, write_interval,
                    forces_patches=wall_patches, cofr=moment_ref, compressible=True, transient=True,
                )
            )
            (run_dir / "system" / "fvSchemes").write_text(templates.fv_schemes_rho_central())
            (run_dir / "system" / "fvSolution").write_text(templates.fv_solution_rho_central())
        else:
            (run_dir / "system" / "controlDict").write_text(
                templates.control_dict(
                    selection.application, solver_settings.max_iterations, write_interval,
                    forces_patches=wall_patches, cofr=moment_ref, compressible=True, transient=not selection.steady,
                )
            )
            (run_dir / "system" / "fvSchemes").write_text(templates.fv_schemes_compressible(selection.steady))
            (run_dir / "system" / "fvSolution").write_text(
                templates.fv_solution_compressible(solver_settings.convergence_residual, selection.steady)
            )
        (run_dir / "0" / "U").write_text(templates.u_field(velocity, wall_patches, symmetry_planes))
        (run_dir / "0" / "p").write_text(templates.p_field_compressible(pressure, wall_patches, symmetry_planes))
        (run_dir / "0" / "T").write_text(
            templates.t_field(
                condition.temperature, wall_patches, condition.adiabatic_wall, condition.wall_temperature,
                symmetry_planes,
            )
        )
    if solver_settings.n_processors > 1:
        (run_dir / "system" / "decomposeParDict").write_text(
            templates.decompose_par_dict(solver_settings.n_processors)
        )

    _write_turbulence_fields(run_dir, solver_settings, wall_patches, k0, omega0, nu_tilda0, symmetry_planes)
    return selection
