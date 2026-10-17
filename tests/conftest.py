"""Pytest fixtures/helpers shared by the whole suite: headless Qt, a shared QApplication, and a subprocess.run stand-in."""  # noqa: 29 (pytest auto-loads conftest.py; never explicitly imported)
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

_WINDOWS_FONT_DIR = "C:/Windows/Fonts"  # noqa: 26 (the OS font directory; inherently absolute, no relative form exists)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32" and Path(_WINDOWS_FONT_DIR).is_dir():
    # The offscreen QPA platform ships no fonts, which zeroes out size hints and would
    # silently defeat any test that checks layout geometry (e.g. clipped-widget checks).
    os.environ.setdefault("QT_QPA_FONTDIR", _WINDOWS_FONT_DIR)


@pytest.fixture(scope="session", autouse=True)  # noqa: 21 (pytest fixture, applied automatically to every test)
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def fake_subprocess_run(returncode: int = 0, stdout: str = "", stderr: str = "") -> Callable[..., subprocess.CompletedProcess]:
    """A subprocess.run monkeypatch target that always returns a fixed CompletedProcess."""

    def _fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)

    return _fake_run


class FakeOpenFOAMReaderTimeMixin:
    """Shared no-op time-selection method for fake pv.OpenFOAMReader test doubles."""

    def set_active_time_value(self, value: float) -> None:  # noqa: 21 (mirrors pyvista's reader API)
        return None
