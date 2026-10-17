"""Ties case generation, execution (WSL/native Linux), mesh-quality gating, caching, and
result parsing into one sweep runner."""
from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from rocketcfd.caching import CaseCache, compute_case_hash
from rocketcfd.flow import SEA_LEVEL_TEMPERATURE, FlowCondition, velocity_alpha_beta, wind_unit
from rocketcfd.geometry import PanelMesh, frontal_area
from rocketcfd.openfoam import case_builder, mesh_quality
from rocketcfd.openfoam.coefficients import Coefficients, from_force_moment
from rocketcfd.openfoam.execution import ExecutionBackend
from rocketcfd.openfoam.runner import check_mesh_command, mesh_commands, solve_commands
from rocketcfd.openfoam.results_parser import find_forces_file, parse_forces_dat, parse_forces_series, parse_u_field
from rocketcfd.openfoam.settings import GroundPlane, MeshSettings, SolverSettings, SymmetryPlane

_METADATA_FILENAME = "case_condition.json"
_DEFAULT_UP = (0.0, 0.0, 1.0)


class MeshQualityFailedError(RuntimeError):
    """Raised when checkMesh fails the configured quality gate (MeshSettings.require_mesh_quality_pass)."""


def _sanitize_name_part(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")


def _run_dir_name(index: int, condition: FlowCondition, model_name: str = "") -> str:
    """Builds a descriptive, sortable run directory name, e.g.
    run_000_body_m0.44_v150ms_a5.0_r1.225."""
    parts = [f"run_{index:03d}"]
    sanitized_model = _sanitize_name_part(model_name)
    if sanitized_model:
        parts.append(sanitized_model)
    parts += [f"m{condition.mach():.2f}", f"v{condition.velocity:.0f}ms", f"a{condition.alpha_deg:.1f}"]
    if condition.beta_deg:
        parts.append(f"b{condition.beta_deg:.1f}")
    parts.append(f"r{condition.density:.3f}")
    return "_".join(parts)


def _unique_run_dir(case_root: Path, index: int, condition: FlowCondition, model_name: str = "") -> Path:
    base = _run_dir_name(index, condition, model_name)
    candidate = case_root / base
    suffix = 2
    while candidate.exists():
        candidate = case_root / f"{base}_{suffix}"
        suffix += 1
    return candidate


@dataclass
class OpenFoamCaseResult:
    condition: FlowCondition
    coefficients: Coefficients
    reference_area: float
    reference_length: float
    force: np.ndarray
    moment: np.ndarray
    case_dir: Path
    application: str = ""


def _save_case_metadata(
    run_dir: Path, condition: FlowCondition, reference_area: float, reference_length: float, application: str,
) -> None:
    """condition is the vehicle-frame FlowCondition (before wind is combined in), so a
    later import can invert the wind vector and recover the same value shown during the
    run; the boundary condition on disk holds the wind-combined (effective) velocity."""
    metadata = {
        "name": condition.name,
        "temperature": condition.temperature,
        "density": condition.density,
        "up": list(condition.up),
        "reference_area": reference_area,
        "reference_length": reference_length,
        "application": application,
        "wind_speed": condition.wind_speed,
        "wind_direction_deg": condition.wind_direction_deg,
        "wind_elevation_deg": condition.wind_elevation_deg,
    }
    (run_dir / _METADATA_FILENAME).write_text(json.dumps(metadata))


def _load_case_metadata(run_dir: Path) -> dict:
    metadata_path = run_dir / _METADATA_FILENAME
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text())


def _has_forces_output(run_dir: Path) -> bool:
    try:
        find_forces_file(run_dir)
    except FileNotFoundError:
        return False
    return True


def _vehicle_condition_from_effective(
    effective: FlowCondition, wind_speed: float, wind_direction_deg: float, wind_elevation_deg: float
) -> FlowCondition:
    """Inverts FlowCondition.effective_condition(): recovers the vehicle-frame velocity/
    alpha/beta that, combined with the given wind, produced this effective (solved)
    condition. Exact inverse of the vector sum in effective_condition()."""
    if wind_speed <= 0.0:
        return effective
    vehicle_vector = effective.velocity * effective.direction_unit() - wind_speed * wind_unit(wind_direction_deg, wind_elevation_deg)
    velocity, alpha_deg, beta_deg = velocity_alpha_beta(vehicle_vector)
    return replace(
        effective, velocity=velocity, alpha_deg=alpha_deg, beta_deg=beta_deg,
        wind_speed=wind_speed, wind_direction_deg=wind_direction_deg, wind_elevation_deg=wind_elevation_deg,
    )


def _load_case_result(run_dir: Path) -> OpenFoamCaseResult:
    """The 0/U boundary condition on disk holds the effective (wind-combined) velocity
    actually solved for; metadata's wind_speed/wind_direction_deg (0 for pre-existing
    cases) lets this recover the original vehicle-frame condition for display while still
    computing coefficients from the effective condition, matching run_openfoam_sweep."""
    metadata = _load_case_metadata(run_dir)
    density = metadata.get("density", 1.225)
    wind_speed = metadata.get("wind_speed", 0.0)
    wind_direction_deg = metadata.get("wind_direction_deg", 0.0)
    wind_elevation_deg = metadata.get("wind_elevation_deg", 0.0)
    velocity, alpha_deg, beta_deg = velocity_alpha_beta(parse_u_field(run_dir))
    effective_condition = FlowCondition(
        name=metadata.get("name", run_dir.name),
        velocity=velocity,
        alpha_deg=alpha_deg,
        beta_deg=beta_deg,
        density=density,
        temperature=metadata.get("temperature", SEA_LEVEL_TEMPERATURE),
        up=tuple(metadata.get("up", _DEFAULT_UP)),
    )
    condition = _vehicle_condition_from_effective(effective_condition, wind_speed, wind_direction_deg, wind_elevation_deg)
    area = metadata.get("reference_area", 0.0)
    length = metadata.get("reference_length", 1.0)
    force, moment = parse_forces_dat(find_forces_file(run_dir))
    coefficients = from_force_moment(effective_condition, force, moment, area, length)
    return OpenFoamCaseResult(
        condition=condition,
        coefficients=coefficients,
        reference_area=area,
        reference_length=length,
        force=force,
        moment=moment,
        case_dir=run_dir,
        application=metadata.get("application", ""),
    )


def load_convergence_history(case: OpenFoamCaseResult) -> tuple[np.ndarray, list[OpenFoamCaseResult]]:
    """Rebuilds one synthetic OpenFoamCaseResult per solver-written timestep from the
    full forces.dat history, for convergence plotting."""
    time, forces, moments = parse_forces_series(find_forces_file(case.case_dir))
    effective_condition = case.condition.effective_condition()
    coefficients = from_force_moment(effective_condition, forces, moments, case.reference_area, case.reference_length)
    snapshots = [
        OpenFoamCaseResult(
            condition=case.condition,
            coefficients=Coefficients(
                cd=float(coefficients.cd[i]),
                cl=float(coefficients.cl[i]),
                cs=float(coefficients.cs[i]),
                cm=coefficients.cm[i],
            ),
            reference_area=case.reference_area,
            reference_length=case.reference_length,
            force=forces[i],
            moment=moments[i],
            case_dir=case.case_dir,
            application=case.application,
        )
        for i in range(len(time))
    ]
    return time, snapshots


def find_case_roots(path: Path) -> list[Path]:
    """Searches `path` at any depth for postProcessing/forces1 output and groups it into
    case roots: a sweep's case_root (parent of one or more run_* directories) or a
    standalone run directory."""
    roots: set[Path] = set()
    for forces_dir in path.rglob("postProcessing/forces1"):
        run_dir = forces_dir.parent.parent
        roots.add(run_dir.parent if run_dir.name.startswith("run_") else run_dir)
    return sorted(roots)


def import_case_results(path: Path) -> list[OpenFoamCaseResult]:
    """Rebuilds sweep results from a single case root on disk."""
    if _has_forces_output(path):
        return [_load_case_result(path)]

    run_dirs = sorted(p for p in path.glob("run_*") if _has_forces_output(p))
    if not run_dirs:
        raise FileNotFoundError(f"no OpenFOAM run cases (with postProcessing/forces1 output) found under {path}")
    return [_load_case_result(run_dir) for run_dir in run_dirs]


def _reference_dims(
    panel_mesh: PanelMesh, direction: np.ndarray, reference_area: float | None, reference_length: float | None
) -> tuple[float, float]:
    area = reference_area if reference_area is not None else frontal_area(panel_mesh, direction)
    if reference_length is not None:
        return area, reference_length
    length = 2.0 * np.sqrt(area / np.pi) if area > 0.0 else 1.0
    return area, length


def _check_mesh_quality(
    mesh_dir: Path, mesh_settings: MeshSettings, execution: ExecutionBackend, on_log: Callable[[str], None]
) -> None:
    log_lines: list[str] = []
    execution.run([check_mesh_command()], mesh_dir, log_lines.append)
    for line in log_lines:
        on_log(line)
    result = mesh_quality.evaluate_mesh_quality(
        mesh_quality.parse_check_mesh_output("\n".join(log_lines)), mesh_settings
    )
    if not result.passed:
        raise MeshQualityFailedError(
            "Mesh quality gate failed:\n" + "\n".join(result.reasons)
            + "\nRefine the mesh settings, or disable the quality gate in advanced mesh settings to solve anyway."
        )


def ensure_mesh(
    panel_mesh: PanelMesh,
    ground_plane: GroundPlane | None,
    mesh_settings: MeshSettings,
    execution: ExecutionBackend,
    on_log: Callable[[str], None],
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
    max_mach: float = 0.0,
    reference_condition: FlowCondition | None = None,
    use_cache: bool = True,
) -> tuple[Path, str]:
    """Builds (or reuses a cached) mesh-only OpenFOAM case: blockMesh/surfaceFeatures/
    snappyHexMesh plus the quality gate. Shared by run_openfoam_sweep (before solving)
    and the GUI's standalone "preview the actual mesh" action, so both paths always use
    the same cache key and quality gate. Returns (mesh_dir, mesh_hash); the hash is
    reused by run_openfoam_sweep to key each condition's own cached result to this mesh."""
    execution.ensure_ready(on_log)
    case_root = execution.case_root
    case_root.mkdir(parents=True, exist_ok=True)
    cache = CaseCache(case_root)

    mesh_dir = case_root / "mesh"
    mesh_hash = compute_case_hash(
        panel_mesh.vertices, panel_mesh.faces, mesh_settings, ground_plane, symmetry_planes, max_mach, reference_condition,
    )
    cached_mesh_dir = cache.lookup(f"mesh_{mesh_hash}") if use_cache else None
    if cached_mesh_dir is not None and (cached_mesh_dir / "constant" / "polyMesh").exists():
        on_log(f"Reusing cached mesh from {cached_mesh_dir}")
        return cached_mesh_dir, mesh_hash

    if mesh_dir.exists():
        shutil.rmtree(mesh_dir)
    on_log(f"Building mesh case in {mesh_dir}")
    case_builder.write_mesh_case(
        mesh_dir, panel_mesh, mesh_settings, ground_plane, symmetry_planes, max_mach, reference_condition,
    )
    on_log("Meshing (blockMesh, surfaceFeatures, snappyHexMesh)...")
    execution.run(mesh_commands(), mesh_dir, on_log)
    on_log("Checking mesh quality (checkMesh)...")
    _check_mesh_quality(mesh_dir, mesh_settings, execution, on_log)
    cache.record(f"mesh_{mesh_hash}", mesh_dir)
    return mesh_dir, mesh_hash


def run_openfoam_sweep(
    panel_mesh: PanelMesh,
    conditions: list[FlowCondition],
    moment_ref: np.ndarray,
    ground_plane: GroundPlane | None,
    mesh_settings: MeshSettings,
    solver_settings: SolverSettings,
    execution: ExecutionBackend,
    reference_area: float | None,
    reference_length: float | None,
    on_log: Callable[[str], None],
    on_progress: Callable[[int, int], None],
    model_name: str = "",
    on_case_result: Callable[[OpenFoamCaseResult], None] | None = None,
    on_case_started: Callable[[str, Path, str], None] | None = None,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
    use_cache: bool = True,
) -> list[OpenFoamCaseResult]:
    execution.ensure_ready(on_log)

    available = execution.available_processors()
    if solver_settings.n_processors > available:
        on_log(
            f"Requested {solver_settings.n_processors} processors but only "
            f"{available} are available; using {available}."
        )
        solver_settings = replace(solver_settings, n_processors=available)

    effective_conditions = [condition.effective_condition() for condition in conditions]
    max_mach = max((condition.mach() for condition in effective_conditions), default=0.0)
    reference_condition = max(effective_conditions, key=lambda condition: condition.velocity, default=None)

    mesh_dir, mesh_hash = ensure_mesh(
        panel_mesh, ground_plane, mesh_settings, execution, on_log, symmetry_planes, max_mach, reference_condition, use_cache,
    )
    case_root = execution.case_root
    cache = CaseCache(case_root)

    results = []
    total = len(conditions)
    for index, condition in enumerate(conditions):
        effective_condition = effective_conditions[index]
        case_hash = compute_case_hash(mesh_hash, condition, solver_settings, moment_ref, reference_area, reference_length)
        cached_run_dir = cache.lookup(case_hash) if use_cache else None
        label = condition.name or str(index)
        if cached_run_dir is not None and _has_forces_output(cached_run_dir):
            on_log(f"[{label}] reusing cached result from {cached_run_dir}")
            result = _load_case_result(cached_run_dir)
        else:
            run_dir = _unique_run_dir(case_root, index, condition, model_name)
            direction = effective_condition.direction_unit()
            area, length = _reference_dims(panel_mesh, direction, reference_area, reference_length)

            on_log(f"[{label}] building run case in {run_dir}")
            selection = case_builder.write_run_case(
                run_dir, mesh_dir, effective_condition, solver_settings, moment_ref, ground_plane, length, symmetry_planes,
            )
            for warning in selection.warnings:
                on_log(f"[{label}] warning: {warning}")
            _save_case_metadata(run_dir, condition, area, length, selection.application)
            on_log(f"[{label}] solving ({selection.application})...")
            if on_case_started is not None:
                on_case_started(label, run_dir, selection.application)
            execution.run(solve_commands(selection.application, solver_settings), run_dir, on_log)

            force, moment = parse_forces_dat(find_forces_file(run_dir))
            coefficients = from_force_moment(effective_condition, force, moment, area, length)
            result = OpenFoamCaseResult(
                condition=condition, coefficients=coefficients, reference_area=area, reference_length=length,
                force=force, moment=moment, case_dir=run_dir, application=selection.application,
            )
            cache.record(case_hash, run_dir)
        results.append(result)
        on_progress(index + 1, total)
        if on_case_result is not None:
            on_case_result(result)
    return results
