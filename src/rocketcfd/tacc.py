"""Generates a TACC (Lonestar6/Stampede-style) SLURM job script for an OpenFOAM case and
submits it over SSH. Uses the `ssh`/`scp` OpenSSH client binaries via subprocess rather
than a Python SSH library, since OpenSSH ships on both Windows 10+ and Linux."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SUBMIT_TIMEOUT_S = 60
TRANSFER_TIMEOUT_S = 1800
_JOB_ID_RE = re.compile(r"Submitted batch job (\d+)")


class TaccSubmissionError(RuntimeError):
    """Raised when SSH/SCP to TACC fails, or sbatch does not report a job id."""


@dataclass
class TaccSettings:
    host: str
    username: str
    allocation: str
    remote_case_root: str
    openfoam_module: str = "openfoam/2306"
    queue: str = "normal"
    nodes: int = 1
    tasks_per_node: int = 56
    walltime: str = "02:00:00"
    ssh_key_path: str = ""


def _ssh_prefix(settings: TaccSettings) -> list[str]:
    command = ["ssh"]
    if settings.ssh_key_path:
        command += ["-i", settings.ssh_key_path]
    command.append(f"{settings.username}@{settings.host}")
    return command


def generate_slurm_script(job_name: str, remote_case_dir: str, application: str, settings: TaccSettings) -> str:
    total_tasks = settings.nodes * settings.tasks_per_node
    lines = [
        "#!/bin/bash",
        f"#SBATCH -J {job_name}",
        f"#SBATCH -o {job_name}.o%j",
        f"#SBATCH -e {job_name}.e%j",
        f"#SBATCH -p {settings.queue}",
        f"#SBATCH -N {settings.nodes}",
        f"#SBATCH -n {total_tasks}",
        f"#SBATCH -t {settings.walltime}",
        f"#SBATCH -A {settings.allocation}",
        "",
        f"module load {settings.openfoam_module}",
        f"cd {remote_case_dir}",
        "decomposePar",
        f"ibrun -n {total_tasks} {application} -parallel",
        "reconstructPar -latestTime",
        "",
    ]
    return "\n".join(lines)


def upload_case(local_case_dir: Path, settings: TaccSettings) -> None:
    remote_target = f"{settings.username}@{settings.host}:{settings.remote_case_root}/"
    try:
        subprocess.run(
            ["scp", "-r", str(local_case_dir), remote_target], check=True, timeout=TRANSFER_TIMEOUT_S, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise TaccSubmissionError(f"scp failed: {exc.stderr.decode(errors='ignore')}") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TaccSubmissionError(f"scp failed: {exc}") from exc


def submit_job(local_case_dir: Path, application: str, settings: TaccSettings) -> str:
    """Uploads local_case_dir, writes a SLURM script for it, and submits via sbatch;
    returns the SLURM job id."""
    upload_case(local_case_dir, settings)
    job_name = local_case_dir.name
    remote_case_dir = f"{settings.remote_case_root}/{job_name}"
    script = generate_slurm_script(job_name, remote_case_dir, application, settings)
    remote_script_path = f"{remote_case_dir}/{job_name}.slurm"
    write_script_command = f"cat > {remote_script_path} << 'EOF'\n{script}\nEOF"

    try:
        subprocess.run(
            [*_ssh_prefix(settings), write_script_command], check=True, timeout=SUBMIT_TIMEOUT_S, capture_output=True,
        )
        submit_result = subprocess.run(
            [*_ssh_prefix(settings), f"cd {remote_case_dir} && sbatch {job_name}.slurm"],
            check=True, timeout=SUBMIT_TIMEOUT_S, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr
        raise TaccSubmissionError(f"SSH command failed: {stderr}") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TaccSubmissionError(f"SSH command failed: {exc}") from exc

    match = _JOB_ID_RE.search(submit_result.stdout)
    if match is None:
        raise TaccSubmissionError(f"sbatch did not report a job id: {submit_result.stdout}")
    return match.group(1)


def job_status(job_id: str, settings: TaccSettings) -> str:
    try:
        result = subprocess.run(
            [*_ssh_prefix(settings), f"squeue -j {job_id} -h -o %T"],
            check=True, timeout=SUBMIT_TIMEOUT_S, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr
        raise TaccSubmissionError(f"SSH command failed: {stderr}") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TaccSubmissionError(f"SSH command failed: {exc}") from exc
    status = result.stdout.strip()
    return status if status else "COMPLETED_OR_UNKNOWN"
