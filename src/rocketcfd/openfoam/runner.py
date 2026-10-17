"""Invokes OpenFOAM utilities/solvers (in WSL or directly on a Linux host), streaming
stdout back line by line."""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from rocketcfd.openfoam.paths import to_wsl_path
from rocketcfd.openfoam.settings import NativeLinuxSettings, SolverSettings, WslSettings

MESH_CHECK_LOG_FILENAME = "log.checkMesh"


def solve_log_filename(application: str) -> str:
    return f"log.{application}"


def mesh_commands() -> list[str]:
    return ["blockMesh", "surfaceFeatures", "snappyHexMesh -overwrite"]


def check_mesh_command() -> str:
    return f"checkMesh | tee {MESH_CHECK_LOG_FILENAME}"


def solve_commands(application: str, solver_settings: SolverSettings) -> list[str]:
    """Tees the solver's output to solve_log_filename(application) in the run directory,
    so residual convergence can be plotted later (see results_parser.parse_residual_history)."""
    log_name = solve_log_filename(application)
    if solver_settings.n_processors > 1:
        return [
            "decomposePar",
            f"mpirun --use-hwthread-cpus -np {solver_settings.n_processors} {application} -parallel | "
            f"tee {log_name}",
            "reconstructPar -latestTime",
        ]
    return [f"{application} | tee {log_name}"]


BASHRC_CANDIDATE_GLOBS = (
    "/usr/lib/openfoam/openfoam*/etc/bashrc",
    "/opt/openfoam*/etc/bashrc",
    "/opt/OpenFOAM/OpenFOAM-*/etc/bashrc",
    "$HOME/OpenFOAM/OpenFOAM-*/etc/bashrc",
)


def _find_bashrc_via(command_prefix: list[str]) -> str | None:
    script = "ls -d " + " ".join(BASHRC_CANDIDATE_GLOBS) + " 2>/dev/null"
    try:
        completed = subprocess.run(
            [*command_prefix, "bash", "-lc", script], capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    matches = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return sorted(matches)[-1] if matches else None


def find_openfoam_bashrc(wsl_settings: WslSettings) -> str | None:
    """Globs common OpenFOAM install locations inside the WSL distro and returns the
    highest-versioned match, or None if nothing was found."""
    return _find_bashrc_via(wsl_command_prefix(wsl_settings) + ["--"])


def find_openfoam_bashrc_native() -> str | None:
    """Same search as find_openfoam_bashrc, run directly on the local Linux host."""
    return _find_bashrc_via([])


def _bashrc_exists_via(command_prefix: list[str], bashrc: str) -> bool:
    try:
        completed = subprocess.run(
            [*command_prefix, "bash", "-lc", f"test -f '{bashrc}'"], capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def bashrc_exists(bashrc: str, wsl_settings: WslSettings) -> bool:
    return _bashrc_exists_via(wsl_command_prefix(wsl_settings) + ["--"], bashrc)


def bashrc_exists_native(bashrc: str) -> bool:
    return _bashrc_exists_via([], bashrc)


def _available_processors_via(command_prefix: list[str]) -> int:
    try:
        completed = subprocess.run(
            [*command_prefix, "bash", "-lc", "nproc"], capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1
    try:
        return max(1, int(completed.stdout.strip()))
    except ValueError:
        return 1


def available_processors(wsl_settings: WslSettings) -> int:
    """Queries WSL's own core count via nproc: mpirun's "slot" count is based on what
    the WSL VM sees, which can differ from the Windows host (e.g. via .wslconfig)."""
    return _available_processors_via(wsl_command_prefix(wsl_settings) + ["--"])


def available_processors_native() -> int:
    return _available_processors_via([])


def list_wsl_distros() -> list[str]:
    if not sys.platform.startswith("win"):
        return []
    try:
        completed = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = completed.stdout
    text = raw.decode("utf-16-le", errors="ignore") if b"\x00" in raw else raw.decode(errors="ignore")
    return [line.strip() for line in text.splitlines() if line.strip()]


def wsl_command_prefix(wsl_settings: WslSettings) -> list[str]:
    command = ["wsl.exe"]
    if wsl_settings.distro:
        command += ["-d", wsl_settings.distro]
    return command


def stream_process(command: list[str], on_line: Callable[[str], None], display_command: str) -> None:
    on_line(f"$ {display_command}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except OSError as exc:
        raise RuntimeError(f"could not launch command: {exc}") from exc

    with process:
        tail: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
            on_line(line)
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
        returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(f"command failed ({display_command}, exit {returncode}):\n" + "\n".join(tail))


def run_commands(
    commands: list[str], case_dir: Path, wsl_settings: WslSettings, on_line: Callable[[str], None],
) -> None:
    wsl_case_dir = to_wsl_path(case_dir)
    for command in commands:
        script = f"set -o pipefail; source '{wsl_settings.openfoam_bashrc}' && cd '{wsl_case_dir}' && {command}"
        stream_process([*wsl_command_prefix(wsl_settings), "--", "bash", "-lc", script], on_line, command)


def run_commands_native(
    commands: list[str], case_dir: Path, native_settings: NativeLinuxSettings, on_line: Callable[[str], None],
) -> None:
    for command in commands:
        script = f"set -o pipefail; source '{native_settings.openfoam_bashrc}' && cd '{case_dir}' && {command}"
        stream_process(["bash", "-lc", script], on_line, command)
