"""Parses OpenFOAM `forces` functionObject output and solver logs into numpy arrays."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_FLOAT_RE = re.compile(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?")
_MIN_SPLIT_ROW_COLUMNS = 7  # time + at least 2 triplets(x,y,z) -- some versions omit porous
_MIN_COMBINED_ROW_COLUMNS = 13  # time + at least 2 force triplets + 2 moment triplets
_INTERNAL_FIELD_RE = re.compile(r"internalField\s+uniform\s*\(([^)]+)\)")
_TIME_RE = re.compile(r"^Time = ([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)")
_RESIDUAL_RE = re.compile(r"Solving for (\w+), Initial residual = ([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)")
_CONTINUITY_RE = re.compile(r"time step continuity errors.*cumulative = ([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)")
CONTINUITY_FIELD = "continuity (cumulative)"


def parse_u_field(run_dir: Path) -> np.ndarray:
    """Reads the freestream velocity vector back out of the 0/U boundary condition
    written by case_builder.write_run_case, so re-imported runs don't need it duplicated
    in metadata."""
    path = run_dir / "0" / "U"
    match = _INTERNAL_FIELD_RE.search(path.read_text())
    if match is None:
        raise ValueError(f"no internalField vector found in {path}")
    return np.array([float(tok) for tok in match.group(1).split()])


def find_forces_file(run_dir: Path) -> Path:
    forces_dir = run_dir / "postProcessing" / "forces1"
    candidates = sorted(forces_dir.glob("*/force.dat")) + sorted(forces_dir.glob("*/forces.dat"))
    if not candidates:
        raise FileNotFoundError(f"no force.dat/forces.dat found under {forces_dir}")
    return candidates[-1]


def find_surface_sample_file(run_dir: Path, surface_name: str = "body") -> Path | None:
    """Finds the latest sampled-surface VTK file written by the surfaceSample
    functionObject (see templates.control_dict), or None if this run predates that
    feature or hasn't written one yet."""
    samples_dir = run_dir / "postProcessing" / "surfaceSample"
    if not samples_dir.exists():
        return None
    candidates = sorted(samples_dir.glob(f"*/{surface_name}.vtk"), key=lambda p: float(p.parent.name))
    return candidates[-1] if candidates else None


def _numeric_rows(path: Path, min_columns: int) -> list[list[float]]:
    rows = []
    for line in Path(path).read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        numbers = [float(tok) for tok in _FLOAT_RE.findall(stripped)]
        if len(numbers) < min_columns:
            continue
        rows.append(numbers)
    return rows


def _last_numeric_row(path: Path, min_columns: int) -> list[float] | None:
    rows = _numeric_rows(path, min_columns)
    return rows[-1] if rows else None


def _sum_triplets(values: list[float]) -> np.ndarray:
    return np.array(values).reshape(-1, 3).sum(axis=0)


def _sum_triplets_series(values: np.ndarray) -> np.ndarray:
    return values.reshape(values.shape[0], -1, 3).sum(axis=1)


def parse_forces_dat(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Reads the last data row(s) written by the `forces` functionObject. Newer OpenFOAM
    versions write forces and moments to separate force.dat/moment.dat files; older versions
    combine both into a single force(s).dat row. Either format may report 2 triplets
    (pressure, viscous) or 3 (pressure, viscous, porous) per vector, so the triplet count
    is inferred from the row length rather than assumed fixed."""
    moment_path = path.parent / "moment.dat"
    if moment_path.exists():
        force_row = _last_numeric_row(path, _MIN_SPLIT_ROW_COLUMNS)
        moment_row = _last_numeric_row(moment_path, _MIN_SPLIT_ROW_COLUMNS)
        if force_row is None or moment_row is None:
            raise ValueError(f"no force/moment data rows found in {path} / {moment_path}")
        return _sum_triplets(force_row[1:]), _sum_triplets(moment_row[1:])

    row = _last_numeric_row(path, _MIN_COMBINED_ROW_COLUMNS)
    if row is None:
        raise ValueError(f"no force data rows found in {path}")
    values = row[1:]
    half = len(values) // 2
    return _sum_triplets(values[:half]), _sum_triplets(values[half:])


def parse_forces_series(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Same file format as parse_forces_dat, but returns every written row (time,
    force, moment) instead of only the last, for convergence-history plotting."""
    moment_path = path.parent / "moment.dat"
    if moment_path.exists():
        force_rows = _numeric_rows(path, _MIN_SPLIT_ROW_COLUMNS)
        moment_rows = _numeric_rows(moment_path, _MIN_SPLIT_ROW_COLUMNS)
        if not force_rows or not moment_rows:
            raise ValueError(f"no force/moment data rows found in {path} / {moment_path}")
        n = min(len(force_rows), len(moment_rows))
        time = np.array([row[0] for row in force_rows[:n]])
        force = _sum_triplets_series(np.array([row[1:] for row in force_rows[:n]]))
        moment = _sum_triplets_series(np.array([row[1:] for row in moment_rows[:n]]))
        return time, force, moment

    rows = _numeric_rows(path, _MIN_COMBINED_ROW_COLUMNS)
    if not rows:
        raise ValueError(f"no force data rows found in {path}")
    arr = np.array(rows)
    time = arr[:, 0]
    values = arr[:, 1:]
    half = values.shape[1] // 2
    return time, _sum_triplets_series(values[:, :half]), _sum_triplets_series(values[:, half:])


def parse_residual_history(log_path: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Parses a solver log for per-field initial-residual and continuity-error
    convergence history, keyed by field name (e.g. "p", "Ux", "k", "omega") plus
    CONTINUITY_FIELD."""
    series: dict[str, list[tuple[float, float]]] = {}
    time = 0.0
    for line in Path(log_path).read_text(errors="ignore").splitlines():
        stripped = line.strip()
        time_match = _TIME_RE.match(stripped)
        if time_match:
            time = float(time_match.group(1))
            continue
        residual_match = _RESIDUAL_RE.search(stripped)
        if residual_match:
            field, residual = residual_match.group(1), float(residual_match.group(2))
            series.setdefault(field, []).append((time, residual))
            continue
        continuity_match = _CONTINUITY_RE.search(stripped)
        if continuity_match:
            series.setdefault(CONTINUITY_FIELD, []).append((time, abs(float(continuity_match.group(1)))))
    return {field: (np.array([t for t, _ in rows]), np.array([r for _, r in rows])) for field, rows in series.items()}
