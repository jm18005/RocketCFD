"""Parses `checkMesh` output and gates a run against the configured quality thresholds."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rocketcfd.openfoam.settings import MeshSettings

_NON_ORTHO_RE = re.compile(r"(?:[Mm]ax non-orthogonality|non-orthogonality\s+Max)\s*[:=]\s*([\d.]+)")
_SKEWNESS_RE = re.compile(r"[Mm]ax skewness\s*[:=]\s*([\d.]+)")
_FAILED_RE = re.compile(r"Failed (\d+) mesh checks?")
_MESH_OK_RE = re.compile(r"Mesh OK\.")


@dataclass
class MeshQualityReport:
    max_non_orthogonality: float | None
    max_skewness: float | None
    checkmesh_reported_ok: bool
    failed_check_count: int


@dataclass
class MeshQualityResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def parse_check_mesh_output(log_text: str) -> MeshQualityReport:
    non_ortho_matches = _NON_ORTHO_RE.findall(log_text)
    skewness_matches = _SKEWNESS_RE.findall(log_text)
    failed_match = _FAILED_RE.search(log_text)
    return MeshQualityReport(
        max_non_orthogonality=float(non_ortho_matches[-1]) if non_ortho_matches else None,
        max_skewness=float(skewness_matches[-1]) if skewness_matches else None,
        checkmesh_reported_ok=_MESH_OK_RE.search(log_text) is not None,
        failed_check_count=int(failed_match.group(1)) if failed_match else 0,
    )


def evaluate_mesh_quality(report: MeshQualityReport, mesh_settings: MeshSettings) -> MeshQualityResult:
    """Gates a run against MeshSettings.max_non_orthogonality/max_skewness, matching the
    thresholds already written into snappyHexMeshDict's meshQualityControls. Disabled by
    MeshSettings.require_mesh_quality_pass=False (always passes, for advanced users who
    want to solve anyway)."""
    if not mesh_settings.require_mesh_quality_pass:
        return MeshQualityResult(True, [])

    reasons = []
    if report.failed_check_count > 0:
        reasons.append(f"checkMesh reported {report.failed_check_count} failed check(s).")
    if report.max_non_orthogonality is not None and report.max_non_orthogonality > mesh_settings.max_non_orthogonality:
        reasons.append(
            f"Max non-orthogonality {report.max_non_orthogonality:.1f} exceeds the configured limit of "
            f"{mesh_settings.max_non_orthogonality:.1f}."
        )
    if report.max_skewness is not None and report.max_skewness > mesh_settings.max_skewness:
        reasons.append(
            f"Max skewness {report.max_skewness:.2f} exceeds the configured limit of {mesh_settings.max_skewness:.2f}."
        )
    return MeshQualityResult(len(reasons) == 0, reasons)
