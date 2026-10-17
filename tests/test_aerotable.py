"""Aerotable CSV generation from a list of solved cases."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from rocketcfd.aerotable import build_aerotable_rows, write_aerotable_csv
from rocketcfd.flow import FlowCondition
from rocketcfd.openfoam.case_result import OpenFoamCaseResult
from rocketcfd.openfoam.coefficients import Coefficients


def _case(name: str, mach_velocity: float, cd: float) -> OpenFoamCaseResult:
    condition = FlowCondition(name=name, velocity=mach_velocity, alpha_deg=0.0, beta_deg=0.0)
    return OpenFoamCaseResult(
        condition=condition,
        coefficients=Coefficients(cd=cd, cl=0.0, cs=0.0, cm=np.zeros(3)),
        reference_area=1.0,
        reference_length=1.0,
        force=np.array([cd, 0.0, 0.0]),
        moment=np.zeros(3),
        case_dir=Path("run_000"),
        application="simpleFoam",
    )


def test_build_aerotable_rows_has_one_row_per_case() -> None:
    cases = [_case("a", 50.0, 0.4), _case("b", 100.0, 0.45)]
    rows = build_aerotable_rows(cases)
    assert len(rows) == 2


def test_build_aerotable_rows_flags_negative_drag() -> None:
    cases = [_case("a", 50.0, -0.2)]
    rows = build_aerotable_rows(cases)
    assert "negative" in rows[0][-1].lower()


def test_write_aerotable_csv_round_trip(tmp_path: Path) -> None:
    cases = [_case("a", 50.0, 0.4)]
    path = tmp_path / "aerotable.csv"
    write_aerotable_csv(path, cases, solver_regimes=["simpleFoam"])
    text = path.read_text()
    assert "cd" in text
    assert "simpleFoam" in text
