"""Platform detection and install-script generation, mocked at the subprocess boundary."""
from __future__ import annotations

import subprocess

import pytest

from rocketcfd import deployment
from tests.conftest import fake_subprocess_run


def test_openfoam_apt_install_script_contains_apt_get() -> None:
    script = deployment.openfoam_apt_install_script("openfoam2306-default")
    assert "apt-get install" in script
    assert "openfoam2306-default" in script


def test_install_wsl_distro_rejects_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deployment, "is_windows_host", lambda: False)
    with pytest.raises(RuntimeError):
        deployment.install_wsl_distro(lambda _line: None)


def test_install_openfoam_native_rejects_on_non_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deployment, "is_linux_host", lambda: False)
    with pytest.raises(RuntimeError):
        deployment.install_openfoam_native(lambda _line: None)


def test_wsl_available_false_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deployment, "is_windows_host", lambda: False)
    assert deployment.wsl_available() is False


def test_wsl_available_true_when_status_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deployment, "is_windows_host", lambda: True)
    monkeypatch.setattr(subprocess, "run", fake_subprocess_run(returncode=0))
    assert deployment.wsl_available() is True
