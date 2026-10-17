"""Parsing OpenFOAM forces/moment.dat files and solver logs into numpy arrays, covering
both split (force.dat + moment.dat) and combined (single forces.dat) file layouts."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rocketcfd.openfoam.results_parser import (
    CONTINUITY_FIELD,
    find_forces_file,
    find_surface_sample_file,
    parse_forces_dat,
    parse_forces_series,
    parse_residual_history,
    parse_u_field,
)

SPLIT_FORCE_ROW = "0.1 (1 2 3) (0.1 0.2 0.3)\n0.2 (1.5 2.5 3.5) (0.15 0.25 0.35)\n"
SPLIT_MOMENT_ROW = "0.1 (0.01 0.02 0.03) (0.001 0.002 0.003)\n0.2 (0.02 0.03 0.04) (0.002 0.003 0.004)\n"
COMBINED_ROW = "0.1 (1 2 3) (0.1 0.2 0.3) (0.01 0.02 0.03) (0.001 0.002 0.003)\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_parse_forces_dat_sums_split_force_and_moment_files(tmp_path: Path) -> None:
    force_path = _write(tmp_path / "force.dat", SPLIT_FORCE_ROW)
    _write(tmp_path / "moment.dat", SPLIT_MOMENT_ROW)
    force, moment = parse_forces_dat(force_path)
    assert force == pytest.approx([1.5 + 0.15, 2.5 + 0.25, 3.5 + 0.35])
    assert moment == pytest.approx([0.02 + 0.002, 0.03 + 0.003, 0.04 + 0.004])


def test_parse_forces_dat_combined_file_splits_force_and_moment_halves(tmp_path: Path) -> None:
    path = _write(tmp_path / "forces.dat", COMBINED_ROW)
    force, moment = parse_forces_dat(path)
    assert force == pytest.approx([1.0 + 0.1, 2.0 + 0.2, 3.0 + 0.3])
    assert moment == pytest.approx([0.01 + 0.001, 0.02 + 0.002, 0.03 + 0.003])


def test_parse_forces_dat_raises_when_no_data_rows(tmp_path: Path) -> None:
    path = _write(tmp_path / "forces.dat", "# just a header\n")
    with pytest.raises(ValueError, match="no force data rows"):
        parse_forces_dat(path)


def test_parse_forces_dat_raises_when_split_files_have_no_rows(tmp_path: Path) -> None:
    force_path = _write(tmp_path / "force.dat", "# header only\n")
    _write(tmp_path / "moment.dat", "# header only\n")
    with pytest.raises(ValueError, match="no force/moment data rows"):
        parse_forces_dat(force_path)


def test_parse_forces_series_returns_every_row_split_format(tmp_path: Path) -> None:
    force_path = _write(tmp_path / "force.dat", SPLIT_FORCE_ROW)
    _write(tmp_path / "moment.dat", SPLIT_MOMENT_ROW)
    time, force, moment = parse_forces_series(force_path)
    assert time.tolist() == [0.1, 0.2]
    assert force.shape == (2, 3)
    assert moment.shape == (2, 3)


def test_parse_forces_series_combined_format(tmp_path: Path) -> None:
    path = _write(tmp_path / "forces.dat", COMBINED_ROW)
    time, force, moment = parse_forces_series(path)
    assert time.tolist() == [0.1]
    assert force.shape == (1, 3)
    assert moment.shape == (1, 3)


def test_find_forces_file_prefers_latest_time_directory(tmp_path: Path) -> None:
    forces_dir = tmp_path / "postProcessing" / "forces1"
    _write(forces_dir / "0.1" / "force.dat", SPLIT_FORCE_ROW)
    latest = _write(forces_dir / "0.2" / "force.dat", SPLIT_FORCE_ROW)
    found = find_forces_file(tmp_path)
    assert found == latest


def test_find_forces_file_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        find_forces_file(tmp_path)


def test_find_surface_sample_file_returns_none_when_absent(tmp_path: Path) -> None:
    assert find_surface_sample_file(tmp_path) is None


def test_find_surface_sample_file_returns_latest_by_time(tmp_path: Path) -> None:
    samples_dir = tmp_path / "postProcessing" / "surfaceSample"
    _write(samples_dir / "50" / "body.vtk", "")
    latest = _write(samples_dir / "100" / "body.vtk", "")
    assert find_surface_sample_file(tmp_path) == latest


def test_parse_u_field_reads_internal_field_vector(tmp_path: Path) -> None:
    _write(tmp_path / "0" / "U", "internalField   uniform (10 0.5 0);\n")
    assert parse_u_field(tmp_path).tolist() == pytest.approx([10.0, 0.5, 0.0])


def test_parse_u_field_raises_when_not_found(tmp_path: Path) -> None:
    _write(tmp_path / "0" / "U", "no vector here\n")
    with pytest.raises(ValueError, match="no internalField"):
        parse_u_field(tmp_path)


def test_parse_residual_history_tracks_fields_and_continuity(tmp_path: Path) -> None:
    log = _write(
        tmp_path / "log.simpleFoam",
        "Time = 1\n"
        "Solving for Ux, Initial residual = 0.5, Final residual = 0.1, No Iterations 3\n"
        "Solving for p, Initial residual = 0.3, Final residual = 0.05, No Iterations 5\n"
        "time step continuity errors : sum local = 1e-05, global = -2e-06, cumulative = 3e-06\n"
        "Time = 2\n"
        "Solving for Ux, Initial residual = 0.1, Final residual = 0.01, No Iterations 2\n",
    )
    history = parse_residual_history(log)
    assert set(history.keys()) == {"Ux", "p", CONTINUITY_FIELD}
    ux_time, ux_values = history["Ux"]
    assert ux_time.tolist() == [1.0, 2.0]
    assert ux_values.tolist() == pytest.approx([0.5, 0.1])
    _continuity_time, continuity_values = history[CONTINUITY_FIELD]
    assert continuity_values.tolist() == pytest.approx([3e-06])


def test_parse_residual_history_empty_log_returns_empty_dict(tmp_path: Path) -> None:
    log = _write(tmp_path / "log.simpleFoam", "nothing useful here\n")
    assert parse_residual_history(log) == {}
