"""Runs the built-in validation suite (sphere, flat plate, slender cone) through the
OpenFOAM automation pipeline and checks results against reference_data within a margin."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import trimesh

from rocketcfd.flow import FlowCondition
from rocketcfd.gas import speed_of_sound, sutherland_viscosity
from rocketcfd.geometry import to_panel_mesh
from rocketcfd.openfoam.case_result import OpenFoamCaseResult, run_openfoam_sweep
from rocketcfd.openfoam.execution import ExecutionBackend
from rocketcfd.openfoam.settings import MeshSettings, SolverSettings
from rocketcfd.validation.reference_data import flat_plate_cf, slender_cone_wave_drag_cd, sphere_cd_reference

DEFAULT_TOLERANCE_PCT = 25.0


@dataclass
class ValidationCase:
    name: str
    geometry: trimesh.Trimesh
    condition: FlowCondition
    reference_value: float
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT


@dataclass
class ValidationResult:
    case_name: str
    computed_value: float
    reference_value: float
    delta_pct: float
    passed: bool


def sphere_case(diameter: float, velocity: float, name: str = "sphere") -> ValidationCase:
    mesh = trimesh.creation.icosphere(radius=diameter / 2.0, subdivisions=3)
    condition = FlowCondition(name=name, velocity=velocity, alpha_deg=0.0, beta_deg=0.0)
    nu = sutherland_viscosity(condition.temperature) / condition.density
    reynolds = velocity * diameter / nu
    return ValidationCase(name, mesh, condition, sphere_cd_reference(reynolds))


def flat_plate_case(length: float, width: float, velocity: float, name: str = "flat_plate") -> ValidationCase:
    mesh = trimesh.creation.box(extents=[length, width, length * 0.02])
    condition = FlowCondition(name=name, velocity=velocity, alpha_deg=0.0, beta_deg=0.0)
    nu = sutherland_viscosity(condition.temperature) / condition.density
    reynolds = velocity * length / nu
    return ValidationCase(name, mesh, condition, flat_plate_cf(reynolds))


def cone_case(half_angle_deg: float, length: float, mach: float, name: str = "cone") -> ValidationCase:
    radius = length * np.tan(np.radians(half_angle_deg))
    mesh = trimesh.creation.cone(radius=radius, height=length)
    condition = FlowCondition(name=name, velocity=mach * speed_of_sound(288.15), alpha_deg=0.0, beta_deg=0.0)
    return ValidationCase(name, mesh, condition, slender_cone_wave_drag_cd(half_angle_deg, mach))


def default_validation_suite() -> list[ValidationCase]:
    return [
        sphere_case(diameter=0.1, velocity=20.0),
        flat_plate_case(length=1.0, width=0.3, velocity=30.0),
        cone_case(half_angle_deg=10.0, length=0.5, mach=2.0),
    ]


def evaluate_case(case: ValidationCase, result: OpenFoamCaseResult) -> ValidationResult:
    # Total Cd approximates mean skin friction for the flat-plate case: pressure drag on
    # a thin plate at zero incidence is negligible.
    computed = result.coefficients.cd
    scale = max(abs(case.reference_value), 1e-9)
    delta_pct = (computed - case.reference_value) / scale * 100.0
    return ValidationResult(case.name, computed, case.reference_value, delta_pct, abs(delta_pct) <= case.tolerance_pct)


def run_validation_suite(
    cases: list[ValidationCase],
    execution: ExecutionBackend,
    mesh_settings: MeshSettings,
    solver_settings: SolverSettings,
    on_log: Callable[[str], None],
) -> list[ValidationResult]:
    results = []
    for case in cases:
        panel_mesh = to_panel_mesh(case.geometry)
        case_settings = replace(execution.settings, case_root=Path(execution.case_root) / "validation" / case.name)
        case_execution = replace(execution, settings=case_settings)
        sweep_results = run_openfoam_sweep(
            panel_mesh=panel_mesh,
            conditions=[case.condition],
            moment_ref=np.zeros(3),
            ground_plane=None,
            mesh_settings=mesh_settings,
            solver_settings=solver_settings,
            execution=case_execution,
            reference_area=None,
            reference_length=None,
            on_log=on_log,
            on_progress=lambda _done, _total: None,
            model_name=case.name,
        )
        results.append(evaluate_case(case, sweep_results[0]))
    return results
