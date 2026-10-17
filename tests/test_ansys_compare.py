"""ANSYS CSV parsing and comparison against OpenFOAM results."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rocketcfd.ansys_compare import compare_to_openfoam, parse_ansys_csv
from rocketcfd.flow import FlowCondition
from rocketcfd.gas import speed_of_sound
from rocketcfd.openfoam.case_result import OpenFoamCaseResult
from rocketcfd.openfoam.coefficients import Coefficients


def _openfoam_case(mach: float, alpha_deg: float, cd: float) -> OpenFoamCaseResult:
    velocity = mach * speed_of_sound(288.15)
    condition = FlowCondition(name="case", velocity=velocity, alpha_deg=alpha_deg, beta_deg=0.0)
    return OpenFoamCaseResult(
        condition=condition,
        coefficients=Coefficients(cd=cd, cl=0.1, cs=0.0, cm=np.zeros(3)),
        reference_area=1.0,
        reference_length=1.0,
        force=np.zeros(3),
        moment=np.zeros(3),
        case_dir=Path("run_000"),
        application="rhoSimpleFoam",
    )


def test_parse_ansys_csv(tmp_path: Path) -> None:
    path = tmp_path / "ansys.csv"
    path.write_text("mach,alpha,cd,cl,cm\n0.5,0,0.42,0.09,0.01\n")
    rows = parse_ansys_csv(path)
    assert len(rows) == 1
    assert rows[0].mach == pytest.approx(0.5)
    assert rows[0].cd == pytest.approx(0.42)


def test_parse_ansys_csv_missing_columns_raises(tmp_path: Path) -> None:
    path = tmp_path / "ansys.csv"
    path.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        parse_ansys_csv(path)


def test_compare_to_openfoam_matches_by_mach_alpha(tmp_path: Path) -> None:
    path = tmp_path / "ansys.csv"
    path.write_text("mach,alpha,cd,cl,cm\n0.5,0,0.40,0.1,0.0\n")
    ansys_rows = parse_ansys_csv(path)
    openfoam_results = [_openfoam_case(0.5, 0.0, 0.42)]
    comparisons = compare_to_openfoam(ansys_rows, openfoam_results)
    cd_comparison = next(c for c in comparisons if c.quantity == "cd")
    assert cd_comparison.delta_pct == pytest.approx(5.0, abs=0.1)


def test_compare_to_openfoam_no_match_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "ansys.csv"
    path.write_text("mach,alpha,cd,cl,cm\n3.0,10,0.40,0.1,0.0\n")
    ansys_rows = parse_ansys_csv(path)
    openfoam_results = [_openfoam_case(0.5, 0.0, 0.42)]
    assert compare_to_openfoam(ansys_rows, openfoam_results) == []
