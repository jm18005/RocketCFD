"""OpenFoamCaseResult import/round-trip and the run_openfoam_sweep orchestration, with a
fake ExecutionBackend standing in for a real OpenFOAM install so the pipeline (mesh once,
per-condition case build, wind-into-BC coupling, forces parsing, caching hooks) is
exercised without actually solving anything."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest
import trimesh

from rocketcfd.flow import FlowCondition
from rocketcfd.geometry import to_panel_mesh
from rocketcfd.openfoam.case_result import import_case_results, run_openfoam_sweep
from rocketcfd.openfoam.coefficients import from_force_moment
from rocketcfd.openfoam.results_parser import parse_u_field
from rocketcfd.openfoam.settings import MeshSettings, SolverSettings

_COMBINED_FORCES_ROW = "0.5 10 0 0 1 0 0 0.1 0 0 0.01 0 0\n"  # time, 2 force triplets, 2 moment triplets
_EXPECTED_FORCE = np.array([11.0, 0.0, 0.0])
_EXPECTED_MOMENT = np.array([0.11, 0.0, 0.0])


def _write_case(run_dir: Path, velocity_vector: np.ndarray, metadata: dict) -> None:
    (run_dir / "0").mkdir(parents=True)
    (run_dir / "0" / "U").write_text(
        f"internalField   uniform ({velocity_vector[0]:.9g} {velocity_vector[1]:.9g} {velocity_vector[2]:.9g});\n"
    )
    (run_dir / "case_condition.json").write_text(json.dumps(metadata))
    forces_dir = run_dir / "postProcessing" / "forces1" / "0"
    forces_dir.mkdir(parents=True)
    (forces_dir / "forces.dat").write_text(_COMBINED_FORCES_ROW)


def test_import_round_trips_condition_without_wind(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_plain"
    metadata = {
        "name": "plain", "temperature": 288.15, "density": 1.225, "up": [0, 0, 1],
        "reference_area": 1.0, "reference_length": 1.0, "application": "simpleFoam",
        "wind_speed": 0.0, "wind_direction_deg": 0.0,
    }
    _write_case(run_dir, np.array([100.0, 0.0, 0.0]), metadata)

    [result] = import_case_results(run_dir)

    assert result.condition.velocity == pytest.approx(100.0)
    assert result.condition.alpha_deg == pytest.approx(0.0, abs=1e-6)
    assert result.force == pytest.approx(_EXPECTED_FORCE)
    assert result.moment == pytest.approx(_EXPECTED_MOMENT)


def test_import_missing_wind_metadata_defaults_to_zero(tmp_path: Path) -> None:
    """Cases written before wind coupling existed have no wind_speed/wind_direction_deg
    key at all; import must treat that the same as no wind, not crash on a missing key."""
    run_dir = tmp_path / "run_old"
    metadata = {
        "name": "old", "temperature": 288.15, "density": 1.225, "up": [0, 0, 1],
        "reference_area": 1.0, "reference_length": 1.0, "application": "simpleFoam",
    }
    _write_case(run_dir, np.array([50.0, 0.0, 0.0]), metadata)

    [result] = import_case_results(run_dir)

    assert result.condition.wind_speed == 0.0
    assert result.condition.velocity == pytest.approx(50.0)


def test_import_recovers_vehicle_condition_and_effective_coefficients_with_wind(tmp_path: Path) -> None:
    vehicle = FlowCondition(name="windy", velocity=100.0, alpha_deg=0.0, beta_deg=0.0, wind_speed=20.0, wind_direction_deg=90.0)
    effective = vehicle.effective_condition()
    assert effective.wind_speed == 0.0  # sanity: effective_condition() folds wind into velocity/alpha/beta

    run_dir = tmp_path / "run_windy"
    metadata = {
        "name": vehicle.name, "temperature": vehicle.temperature, "density": vehicle.density,
        "up": list(vehicle.up), "reference_area": 1.0, "reference_length": 1.0, "application": "simpleFoam",
        "wind_speed": vehicle.wind_speed, "wind_direction_deg": vehicle.wind_direction_deg,
    }
    _write_case(run_dir, effective.velocity * effective.direction_unit(), metadata)

    [result] = import_case_results(run_dir)

    assert result.condition.velocity == pytest.approx(vehicle.velocity, abs=1e-6)
    assert result.condition.alpha_deg == pytest.approx(vehicle.alpha_deg, abs=1e-6)
    assert result.condition.beta_deg == pytest.approx(vehicle.beta_deg, abs=1e-6)
    assert result.condition.wind_speed == pytest.approx(20.0)
    assert result.condition.wind_direction_deg == pytest.approx(90.0)

    expected = from_force_moment(effective, _EXPECTED_FORCE, _EXPECTED_MOMENT, 1.0, 1.0)
    assert result.coefficients.cd == pytest.approx(expected.cd)
    assert result.coefficients.cl == pytest.approx(expected.cl)


@dataclass
class _FakeExecutionBackend:
    """Stands in for WslExecutionBackend/NativeLinuxExecutionBackend: never shells out,
    just fabricates the on-disk side effects a real mesh+solve would have left behind so
    the rest of run_openfoam_sweep's pipeline (parsing, caching, callbacks) runs for real."""

    case_root: Path
    run_calls: list[tuple[list[str], Path]] = field(default_factory=list)

    def ensure_ready(self, on_log: object) -> None:  # noqa: 21 (ExecutionBackend protocol)
        return None

    def available_processors(self) -> int:
        return 1

    def run(self, commands: list[str], case_dir: Path, on_log: object) -> None:
        self.run_calls.append((commands, case_dir))
        joined = " ".join(commands)
        if "blockMesh" in joined:
            (case_dir / "constant" / "polyMesh").mkdir(parents=True, exist_ok=True)
        elif "tee log." in joined and "checkMesh" not in joined:
            forces_dir = case_dir / "postProcessing" / "forces1" / "0"
            forces_dir.mkdir(parents=True, exist_ok=True)
            (forces_dir / "forces.dat").write_text(_COMBINED_FORCES_ROW)


def _sphere_panel_mesh() -> object:
    return to_panel_mesh(trimesh.creation.icosphere(radius=0.5, subdivisions=1))


def test_run_openfoam_sweep_couples_wind_into_solved_bc_and_reports_vehicle_condition(tmp_path: Path) -> None:
    panel_mesh = _sphere_panel_mesh()
    condition = FlowCondition(name="alpha=0", velocity=100.0, alpha_deg=0.0, beta_deg=0.0, wind_speed=20.0, wind_direction_deg=90.0)
    backend = _FakeExecutionBackend(case_root=tmp_path / "cases")
    started: list[tuple[str, Path, str]] = []

    results = run_openfoam_sweep(
        panel_mesh, [condition], np.zeros(3), None, MeshSettings(), SolverSettings(n_processors=1), backend,
        None, None, on_log=lambda _line: None, on_progress=lambda _done, _total: None,
        on_case_started=lambda label, run_dir, application: started.append((label, run_dir, application)),
        use_cache=False,
    )

    [result] = results
    assert result.condition.velocity == pytest.approx(100.0, abs=1e-6)
    assert result.condition.alpha_deg == pytest.approx(0.0, abs=1e-6)

    assert len(started) == 1
    label, run_dir, application = started[0]
    assert label == condition.name
    assert application == "simpleFoam"
    # The solved BC must reflect the wind-combined (effective) velocity, not the raw
    # vehicle velocity -- i.e. a nonzero Y-component from the 90-degree crosswind.
    solved_velocity = parse_u_field(run_dir)
    assert solved_velocity[1] == pytest.approx(condition.wind_speed, abs=1e-6)
