"""Execution backends: bashrc auto-detect/fallback and command dispatch, mocked at the
openfoam.runner boundary so no real WSL/Linux host is required."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rocketcfd.openfoam import runner
from rocketcfd.openfoam.execution import NativeLinuxExecutionBackend, WslExecutionBackend
from rocketcfd.openfoam.settings import NativeLinuxSettings, WslSettings


def test_wsl_ensure_ready_noop_when_bashrc_already_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "bashrc_exists", lambda _bashrc, _settings: True)
    backend = WslExecutionBackend(WslSettings(openfoam_bashrc="/opt/of/etc/bashrc"))
    logs: list[str] = []
    backend.ensure_ready(logs.append)
    assert logs == []
    assert backend.settings.openfoam_bashrc == "/opt/of/etc/bashrc"


def test_wsl_ensure_ready_auto_detects_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "bashrc_exists", lambda _bashrc, _settings: False)
    monkeypatch.setattr(runner, "find_openfoam_bashrc", lambda _settings: "/opt/openfoam2312/etc/bashrc")
    backend = WslExecutionBackend(WslSettings(openfoam_bashrc=""))
    logs: list[str] = []
    backend.ensure_ready(logs.append)
    assert backend.settings.openfoam_bashrc == "/opt/openfoam2312/etc/bashrc"
    assert any("auto-detected" in line for line in logs)


def test_wsl_ensure_ready_raises_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "bashrc_exists", lambda _bashrc, _settings: False)
    monkeypatch.setattr(runner, "find_openfoam_bashrc", lambda _settings: None)
    backend = WslExecutionBackend(WslSettings(openfoam_bashrc=""))
    with pytest.raises(RuntimeError, match="Could not find"):
        backend.ensure_ready(lambda _line: None)


def test_wsl_backend_case_root_and_processors_and_run_delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "available_processors", lambda _settings: 6)
    calls: list[Any] = []
    monkeypatch.setattr(runner, "run_commands", lambda *args: calls.append(args))
    backend = WslExecutionBackend(WslSettings(case_root=tmp_path))
    assert backend.case_root == tmp_path
    assert backend.available_processors() == 6
    backend.run(["blockMesh"], tmp_path, lambda _line: None)
    assert len(calls) == 1


def test_native_ensure_ready_auto_detects_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "bashrc_exists_native", lambda _bashrc: False)
    monkeypatch.setattr(runner, "find_openfoam_bashrc_native", lambda: "/opt/openfoam2312/etc/bashrc")
    backend = NativeLinuxExecutionBackend(NativeLinuxSettings(openfoam_bashrc=""))
    backend.ensure_ready(lambda _line: None)
    assert backend.settings.openfoam_bashrc == "/opt/openfoam2312/etc/bashrc"


def test_native_ensure_ready_raises_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "bashrc_exists_native", lambda _bashrc: False)
    monkeypatch.setattr(runner, "find_openfoam_bashrc_native", lambda: None)
    backend = NativeLinuxExecutionBackend(NativeLinuxSettings(openfoam_bashrc=""))
    with pytest.raises(RuntimeError, match="Could not find"):
        backend.ensure_ready(lambda _line: None)


def test_native_backend_case_root_and_processors_and_run_delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "available_processors_native", lambda: 4)
    calls: list[Any] = []
    monkeypatch.setattr(runner, "run_commands_native", lambda *args: calls.append(args))
    backend = NativeLinuxExecutionBackend(NativeLinuxSettings(case_root=tmp_path))
    assert backend.case_root == tmp_path
    assert backend.available_processors() == 4
    backend.run(["blockMesh"], tmp_path, lambda _line: None)
    assert len(calls) == 1
