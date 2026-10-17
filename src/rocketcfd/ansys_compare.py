"""Reads an ANSYS-exported results table (Fluent/CFD-Post report CSV) and compares its
Cd/Cl/Cm values against a matching set of OpenFOAM sweep results."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rocketcfd.openfoam.case_result import OpenFoamCaseResult

DEFAULT_COLUMN_MAP = {
    "mach": "mach",
    "alpha_deg": "alpha",
    "cd": "cd",
    "cl": "cl",
    "cm": "cm",
}
MATCH_TOLERANCE = 1e-3


@dataclass
class AnsysRow:
    mach: float
    alpha_deg: float
    cd: float | None
    cl: float | None
    cm: float | None


@dataclass
class ComparisonResult:
    mach: float
    alpha_deg: float
    quantity: str
    ansys_value: float
    openfoam_value: float
    delta_pct: float


def _find_column(headers: list[str], candidate: str) -> str | None:
    lowered = {h.strip().lower(): h for h in headers}
    return lowered.get(candidate.strip().lower())


def parse_ansys_csv(path: str | Path, column_map: dict[str, str] | None = None) -> list[AnsysRow]:
    """column_map maps our canonical field names (mach, alpha_deg, cd, cl, cm) to the
    header names actually used in the exported CSV; unmapped optional fields (cd/cl/cm)
    are left as None if no matching column is found."""
    mapping = {**DEFAULT_COLUMN_MAP, **(column_map or {})}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        resolved = {field: _find_column(headers, header) for field, header in mapping.items()}
        if resolved["mach"] is None or resolved["alpha_deg"] is None:
            raise ValueError(
                f"Could not find 'mach'/'alpha' columns in {path} (headers: {headers}). "
                "Pass an explicit column_map."
            )
        rows = []
        for record in reader:
            rows.append(
                AnsysRow(
                    mach=float(record[resolved["mach"]]),
                    alpha_deg=float(record[resolved["alpha_deg"]]),
                    cd=float(record[resolved["cd"]]) if resolved["cd"] else None,
                    cl=float(record[resolved["cl"]]) if resolved["cl"] else None,
                    cm=float(record[resolved["cm"]]) if resolved["cm"] else None,
                )
            )
        return rows


def _matches(ansys_row: AnsysRow, case: OpenFoamCaseResult) -> bool:
    return (
        abs(ansys_row.mach - case.condition.mach()) < MATCH_TOLERANCE
        and abs(ansys_row.alpha_deg - case.condition.alpha_deg) < MATCH_TOLERANCE
    )


def compare_to_openfoam(ansys_rows: list[AnsysRow], openfoam_results: list[OpenFoamCaseResult]) -> list[ComparisonResult]:
    """Matches rows by (mach, alpha_deg) and reports percent difference for whichever of
    cd/cl/cm the ANSYS row provides; unmatched ANSYS rows are silently skipped."""
    comparisons = []
    for ansys_row in ansys_rows:
        case = next((c for c in openfoam_results if _matches(ansys_row, c)), None)
        if case is None:
            continue
        for quantity, ansys_value, openfoam_value in (
            ("cd", ansys_row.cd, case.coefficients.cd),
            ("cl", ansys_row.cl, case.coefficients.cl),
            ("cm", ansys_row.cm, float(case.coefficients.cm[1])),
        ):
            if ansys_value is None:
                continue
            scale = max(abs(ansys_value), 1e-9)
            delta_pct = (openfoam_value - ansys_value) / scale * 100.0
            comparisons.append(
                ComparisonResult(ansys_row.mach, ansys_row.alpha_deg, quantity, ansys_value, openfoam_value, delta_pct)
            )
    return comparisons
