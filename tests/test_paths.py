"""Windows -> WSL path translation."""
from __future__ import annotations

from pathlib import Path, PureWindowsPath

import pytest

from rocketcfd.openfoam.paths import to_wsl_path


def test_to_wsl_path_maps_drive_letter_to_mnt(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_resolved = PureWindowsPath(r"C:\Users\x\case")  # noqa: 26 (fake path stubbed via monkeypatch, not a real filesystem location)
    monkeypatch.setattr(Path, "resolve", lambda self: fake_resolved)
    assert to_wsl_path(Path("ignored")) == "/mnt/c/Users/x/case"


def test_to_wsl_path_lowercases_drive_letter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_resolved = PureWindowsPath(r"D:\cases")  # noqa: 26 (fake path stubbed via monkeypatch, not a real filesystem location)
    monkeypatch.setattr(Path, "resolve", lambda self: fake_resolved)
    assert to_wsl_path(Path("ignored")) == "/mnt/d/cases"


def test_to_wsl_path_root_of_drive_has_no_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_resolved = PureWindowsPath(r"C:\\")  # noqa: 26 (fake path stubbed via monkeypatch, not a real filesystem location)
    monkeypatch.setattr(Path, "resolve", lambda self: fake_resolved)
    assert to_wsl_path(Path("ignored")) == "/mnt/c"
