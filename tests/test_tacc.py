"""TACC SLURM script generation and submission, mocked at the subprocess boundary."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from rocketcfd.tacc import TaccSettings, TaccSubmissionError, generate_slurm_script, job_status, submit_job

SETTINGS = TaccSettings(
    host="ls6.tacc.utexas.edu", username="jdoe", allocation="MyAlloc", remote_case_root="/scratch/jdoe/cases",
    nodes=2, tasks_per_node=10,
)


def test_generate_slurm_script_contains_sbatch_directives() -> None:
    script = generate_slurm_script("job1", "/scratch/jdoe/cases/job1", "rhoSimpleFoam", SETTINGS)
    assert "#SBATCH -N 2" in script
    assert "#SBATCH -n 20" in script
    assert "#SBATCH -A MyAlloc" in script
    assert "ibrun -n 20 rhoSimpleFoam -parallel" in script


def test_submit_job_parses_job_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    case_dir = tmp_path / "run_000"
    case_dir.mkdir()

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0] == "scp":
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if "sbatch" in args[-1]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 12345\n", stderr="")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    job_id = submit_job(case_dir, "rhoSimpleFoam", SETTINGS)
    assert job_id == "12345"


def test_submit_job_raises_on_scp_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    case_dir = tmp_path / "run_000"
    case_dir.mkdir()

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, args, stderr=b"connection refused")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(TaccSubmissionError):
        submit_job(case_dir, "rhoSimpleFoam", SETTINGS)


def test_job_status_returns_state(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="RUNNING\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert job_status("12345", SETTINGS) == "RUNNING"
