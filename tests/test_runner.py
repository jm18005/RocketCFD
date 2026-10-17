"""Solver command generation and processor-count queries, mocked at the subprocess boundary."""
from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from rocketcfd.openfoam import runner
from rocketcfd.openfoam.runner import (
    available_processors,
    available_processors_native,
    bashrc_exists,
    bashrc_exists_native,
    find_openfoam_bashrc,
    find_openfoam_bashrc_native,
    list_wsl_distros,
    solve_commands,
    solve_log_filename,
    stream_process,
    wsl_command_prefix,
)
from rocketcfd.openfoam.settings import SolverSettings, WslSettings
from tests.conftest import fake_subprocess_run


def test_available_processors_parses_nproc_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="8\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert available_processors(WslSettings()) == 8
    assert available_processors_native() == 8


def test_available_processors_falls_back_to_one_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise OSError("wsl.exe not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert available_processors(WslSettings()) == 1


def test_solve_commands_single_process_uses_application_name() -> None:
    single = solve_commands("simpleFoam", SolverSettings(n_processors=1))
    assert single == [f"simpleFoam | tee {solve_log_filename('simpleFoam')}"]


def test_solve_commands_parallel_uses_mpirun_and_reconstruct() -> None:
    parallel = solve_commands("rhoSimpleFoam", SolverSettings(n_processors=4))
    assert parallel[0] == "decomposePar"
    assert "mpirun" in parallel[1]
    assert "rhoSimpleFoam" in parallel[1]
    assert parallel[2] == "reconstructPar -latestTime"


def test_solve_log_filename_is_per_application() -> None:
    assert solve_log_filename("rhoCentralFoam") == "log.rhoCentralFoam"


def test_wsl_command_prefix_adds_distro_flag_when_set() -> None:
    assert wsl_command_prefix(WslSettings(distro="Ubuntu")) == ["wsl.exe", "-d", "Ubuntu"]
    assert wsl_command_prefix(WslSettings(distro="")) == ["wsl.exe"]


def test_find_openfoam_bashrc_returns_highest_versioned_match(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = "/opt/openfoam2306/etc/bashrc\n/opt/openfoam2312/etc/bashrc\n"

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert find_openfoam_bashrc(WslSettings()) == "/opt/openfoam2312/etc/bashrc"
    assert find_openfoam_bashrc_native() == "/opt/openfoam2312/etc/bashrc"


def test_find_openfoam_bashrc_returns_none_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert find_openfoam_bashrc(WslSettings()) is None


def test_find_openfoam_bashrc_returns_none_on_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise OSError("wsl.exe not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert find_openfoam_bashrc(WslSettings()) is None


def test_bashrc_exists_reflects_return_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", fake_subprocess_run(returncode=0))
    assert bashrc_exists("/opt/openfoam/etc/bashrc", WslSettings()) is True
    assert bashrc_exists_native("/opt/openfoam/etc/bashrc") is True


def test_bashrc_exists_false_when_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert bashrc_exists("/nowhere", WslSettings()) is False


def test_list_wsl_distros_returns_empty_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert list_wsl_distros() == []


def test_list_wsl_distros_decodes_utf16_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="Ubuntu\r\ndocker-desktop\r\n".encode("utf-16-le"))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert list_wsl_distros() == ["Ubuntu", "docker-desktop"]


def test_list_wsl_distros_decodes_plain_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"Ubuntu\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert list_wsl_distros() == ["Ubuntu"]


def test_list_wsl_distros_returns_empty_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise OSError("wsl.exe not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert list_wsl_distros() == []


class _FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def __iter__(self) -> Any:
        return iter(self._lines)


class _FakeProcess:
    def __init__(self, lines: list[str], returncode: int) -> None:
        self.stdout = _FakeStdout(lines)
        self._returncode = returncode

    def wait(self) -> int:
        return self._returncode

    def __enter__(self) -> "_FakeProcess":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None


def test_stream_process_reports_each_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: _FakeProcess(["a\n", "b\n"], 0))
    seen: list[str] = []
    stream_process(["echo"], seen.append, "echo hi")
    assert seen == ["$ echo hi", "a", "b"]


def test_stream_process_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: _FakeProcess(["boom\n"], 1))
    with pytest.raises(RuntimeError, match="exit 1"):
        stream_process(["false"], lambda _line: None, "false")


def test_stream_process_wraps_launch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_oserror(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("no such file")

    monkeypatch.setattr(subprocess, "Popen", raise_oserror)
    with pytest.raises(RuntimeError, match="could not launch"):
        stream_process(["missing"], lambda _line: None, "missing")


def test_run_commands_invokes_stream_process_per_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    calls: list[str] = []
    monkeypatch.setattr(runner, "to_wsl_path", lambda _p: "/mnt/c/case")
    monkeypatch.setattr(runner, "stream_process", lambda command, on_line, display: calls.append(display))
    runner.run_commands(["blockMesh", "snappyHexMesh"], tmp_path, WslSettings(openfoam_bashrc="/opt/of/etc/bashrc"), lambda _l: None)
    assert calls == ["blockMesh", "snappyHexMesh"]
