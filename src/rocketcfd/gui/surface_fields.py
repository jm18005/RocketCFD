"""Extracts renderable scalar fields from an OpenFOAM sampled-surface VTK file."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pyvista as pv

from rocketcfd.flow import FlowCondition
from rocketcfd.openfoam.results_parser import find_surface_sample_file


def _field_array(surface: pv.PolyData, name: str) -> np.ndarray | None:
    if name in surface.cell_data:
        return np.asarray(surface.cell_data[name])
    if name in surface.point_data:
        return np.asarray(surface.point_data[name])
    return None


def _pressure(surface: pv.PolyData, _condition: FlowCondition) -> np.ndarray | None:
    return _field_array(surface, "p")


def _wall_shear_magnitude(surface: pv.PolyData, _condition: FlowCondition) -> np.ndarray | None:
    tau = _field_array(surface, "wallShearStress")
    return None if tau is None else np.linalg.norm(tau, axis=1)


def _skin_friction(surface: pv.PolyData, condition: FlowCondition) -> np.ndarray | None:
    tau = _field_array(surface, "wallShearStress")
    if tau is None:
        return None
    q = condition.dynamic_pressure()
    return np.linalg.norm(tau, axis=1) / q if q > 0.0 else None


def _y_plus(surface: pv.PolyData, _condition: FlowCondition) -> np.ndarray | None:
    return _field_array(surface, "yPlus")


SURFACE_SCALAR_FIELDS: dict[str, Callable[[pv.PolyData, FlowCondition], np.ndarray | None]] = {
    "Pressure (Pa)": _pressure,
    "Wall shear stress magnitude (Pa)": _wall_shear_magnitude,
    "Skin friction coefficient (Cf)": _skin_friction,
    "y+": _y_plus,
}


def load_case_surface(run_dir: Path) -> pv.PolyData | None:
    path = find_surface_sample_file(run_dir)
    return None if path is None else pv.read(str(path))
