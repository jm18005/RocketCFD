"""Mesh-boundary-surface loading for the 3D preview, with pyvista's OpenFOAM reader
mocked (no real OpenFOAM install is available in tests)."""
from __future__ import annotations

from pathlib import Path

import pyvista as pv
import pytest

from rocketcfd.gui.mesh_preview import load_mesh_boundary_surface
from tests.conftest import FakeOpenFOAMReaderTimeMixin


def test_returns_none_when_no_polymesh_exists(tmp_path: Path) -> None:
    assert load_mesh_boundary_surface(tmp_path) is None


class _FakeReader(FakeOpenFOAMReaderTimeMixin):
    def __init__(self, path: str) -> None:
        self.path = path
        self.time_values: list[float] = [0.0, 1.0]
        self.enabled_patches: list[str] = []

    def disable_all_patch_arrays(self) -> None:
        return None

    def enable_patch_array(self, name: str) -> None:
        self.enabled_patches.append(name)

    def read(self) -> pv.MultiBlock:
        return pv.MultiBlock({"internalMesh": pv.UnstructuredGrid(), "boundary": pv.MultiBlock({"body": pv.Sphere()})})


def test_loads_body_patch_surface_via_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "constant" / "polyMesh").mkdir(parents=True)
    monkeypatch.setattr(pv, "OpenFOAMReader", _FakeReader)

    surface = load_mesh_boundary_surface(tmp_path)

    assert surface is not None
    assert surface.n_points > 0
    assert (tmp_path / "preview.foam").exists()


class _RaisingReader:
    def __init__(self, path: str) -> None:
        raise RuntimeError("unsupported OpenFOAM version")


def test_returns_none_when_reader_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "constant" / "polyMesh").mkdir(parents=True)
    monkeypatch.setattr(pv, "OpenFOAMReader", _RaisingReader)

    assert load_mesh_boundary_surface(tmp_path) is None
