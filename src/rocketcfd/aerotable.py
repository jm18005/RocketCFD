"""Builds an aerotable CSV (swept flight-condition columns + force/moment coefficients)
from a list of solved OpenFOAM cases, with sanity-check flags attached per row."""
from __future__ import annotations

import csv
from pathlib import Path

from rocketcfd.openfoam.case_result import OpenFoamCaseResult
from rocketcfd.sanity_checks import build_sanity_report

AEROTABLE_HEADERS = [
    "case", "mach", "velocity_ms", "alpha_deg", "beta_deg", "density_kgm3", "temperature_k",
    "cd", "cl", "cs", "cmx", "cmy", "cmz", "solver_regime", "sanity_flags",
]


def build_aerotable_rows(case_results: list[OpenFoamCaseResult], solver_regimes: list[str] | None = None) -> list[list[str]]:
    cd_values = [case.coefficients.cd for case in case_results]
    mach_values = [case.condition.mach() for case in case_results]
    sanity = build_sanity_report(cd_values, mach_values)
    flags_by_index: dict[int, list[str]] = {}
    for flag in sanity.flags:
        flags_by_index.setdefault(flag.case_index, []).append(flag.message)

    regimes = solver_regimes if solver_regimes is not None else [""] * len(case_results)
    rows = []
    for i, case in enumerate(case_results):
        rows.append(
            [
                case.condition.name,
                f"{mach_values[i]:.6g}",
                f"{case.condition.velocity:.6g}",
                f"{case.condition.alpha_deg:.6g}",
                f"{case.condition.beta_deg:.6g}",
                f"{case.condition.density:.6g}",
                f"{case.condition.temperature:.6g}",
                f"{case.coefficients.cd:.6g}",
                f"{case.coefficients.cl:.6g}",
                f"{case.coefficients.cs:.6g}",
                f"{float(case.coefficients.cm[0]):.6g}",
                f"{float(case.coefficients.cm[1]):.6g}",
                f"{float(case.coefficients.cm[2]):.6g}",
                regimes[i],
                "; ".join(flags_by_index.get(i, [])),
            ]
        )
    return rows


def write_aerotable_csv(path: str | Path, case_results: list[OpenFoamCaseResult], solver_regimes: list[str] | None = None) -> None:
    rows = build_aerotable_rows(case_results, solver_regimes)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(AEROTABLE_HEADERS)
        writer.writerows(rows)
