"""checkMesh output parsing and the mesh-quality pass/fail gate."""
from __future__ import annotations

from rocketcfd.openfoam.mesh_quality import evaluate_mesh_quality, parse_check_mesh_output
from rocketcfd.openfoam.settings import MeshSettings

PASSING_LOG = """
Checking geometry...
Mesh non-orthogonality Max: 42.1 average: 10.2
Max skewness = 1.8 OK.
Mesh OK.
"""

FAILING_LOG = """
Checking geometry...
***Max non-orthogonality = 72.4, this may impair the quality of the results
***Max skewness = 6.1, this may impair the quality of the results
Failed 2 mesh checks.
"""


def test_parse_passing_log() -> None:
    report = parse_check_mesh_output(PASSING_LOG)
    assert report.max_non_orthogonality == 42.1
    assert report.max_skewness == 1.8
    assert report.checkmesh_reported_ok
    assert report.failed_check_count == 0


def test_parse_failing_log() -> None:
    report = parse_check_mesh_output(FAILING_LOG)
    assert report.max_non_orthogonality == 72.4
    assert report.max_skewness == 6.1
    assert not report.checkmesh_reported_ok
    assert report.failed_check_count == 2


def test_evaluate_passes_within_thresholds() -> None:
    report = parse_check_mesh_output(PASSING_LOG)
    result = evaluate_mesh_quality(report, MeshSettings())
    assert result.passed


def test_evaluate_fails_outside_thresholds() -> None:
    report = parse_check_mesh_output(FAILING_LOG)
    result = evaluate_mesh_quality(report, MeshSettings())
    assert not result.passed
    assert result.reasons


def test_evaluate_gate_disabled_always_passes() -> None:
    report = parse_check_mesh_output(FAILING_LOG)
    settings = MeshSettings(require_mesh_quality_pass=False)
    result = evaluate_mesh_quality(report, settings)
    assert result.passed
