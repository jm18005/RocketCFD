"""Volumetric flow-field loading (velocity-magnitude slices, flow-path traces), with
pyvista's OpenFOAM reader mocked (no real OpenFOAM install is available in tests) but the
actual pyvista filters exercised for real against a small synthetic grid."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv
import pytest

from rocketcfd.gui.volume_fields import (
    VELOCITY_MAGNITUDE_FIELD,
    flow_path_traces,
    load_case_volume,
    velocity_magnitude_slice,
)
from tests.conftest import FakeOpenFOAMReaderTimeMixin


def _uniform_flow_grid() -> pv.UnstructuredGrid:
    grid = pv.ImageData(dimensions=(6, 6, 6), spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0))
    grid.point_data["U"] = np.tile(np.array([3.0, 4.0, 0.0]), (grid.n_points, 1))
    return grid.cast_to_unstructured_grid()


def test_returns_none_when_no_polymesh_exists(tmp_path: Path) -> None:
    assert load_case_volume(tmp_path) is None


class _FakeReader(FakeOpenFOAMReaderTimeMixin):
    def __init__(self, path: str) -> None:
        self.path = path
        self.time_values: list[float] = [0.0, 1.0]

    def read(self) -> pv.MultiBlock:
        return pv.MultiBlock({"internalMesh": _uniform_flow_grid(), "boundary": pv.MultiBlock({})})


def test_load_case_volume_adds_velocity_magnitude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "constant" / "polyMesh").mkdir(parents=True)
    monkeypatch.setattr(pv, "OpenFOAMReader", _FakeReader)

    volume = load_case_volume(tmp_path)

    assert volume is not None
    assert VELOCITY_MAGNITUDE_FIELD in volume.point_data
    assert np.asarray(volume.point_data[VELOCITY_MAGNITUDE_FIELD])[0] == pytest.approx(5.0)  # 3-4-5 triangle


class _NoVelocityReader(_FakeReader):
    def read(self) -> pv.MultiBlock:
        grid = pv.ImageData(dimensions=(3, 3, 3)).cast_to_unstructured_grid()
        return pv.MultiBlock({"internalMesh": grid, "boundary": pv.MultiBlock({})})


def test_load_case_volume_returns_none_without_u_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "constant" / "polyMesh").mkdir(parents=True)
    monkeypatch.setattr(pv, "OpenFOAMReader", _NoVelocityReader)

    assert load_case_volume(tmp_path) is None


def test_velocity_magnitude_slice_returns_polydata_with_field() -> None:
    grid = _uniform_flow_grid()
    grid.point_data[VELOCITY_MAGNITUDE_FIELD] = np.linalg.norm(np.asarray(grid.point_data["U"]), axis=1)

    sliced = velocity_magnitude_slice(grid, normal="y")

    assert isinstance(sliced, pv.PolyData)
    assert VELOCITY_MAGNITUDE_FIELD in sliced.point_data


def test_flow_path_traces_returns_polylines_along_uniform_flow() -> None:
    grid = _uniform_flow_grid()

    traces = flow_path_traces(grid, source_center=(2.5, 2.5, 2.5), source_radius=0.5, n_points=5)

    assert isinstance(traces, pv.PolyData)
    assert traces.n_points > 0
