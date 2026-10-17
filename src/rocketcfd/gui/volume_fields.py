"""Loads the OpenFOAM volumetric flow field (internalMesh + U) for a solved case, for
velocity-magnitude contour slices and flow-path traces -- distinct from surface_fields.py,
which only covers scalar fields sampled on the body's own surface."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv

VOLUME_FOAM_FILENAME = "volume.foam"
VELOCITY_MAGNITUDE_FIELD = "U_magnitude"


def _field_array(mesh: pv.DataSet, name: str) -> np.ndarray | None:
    if name in mesh.point_data:
        return np.asarray(mesh.point_data[name])
    if name in mesh.cell_data:
        return np.asarray(mesh.cell_data[name])
    return None


def _with_velocity_magnitude(mesh: pv.UnstructuredGrid) -> pv.UnstructuredGrid:
    result = mesh.copy()
    if "U" in result.point_data:
        result.point_data[VELOCITY_MAGNITUDE_FIELD] = np.linalg.norm(np.asarray(result.point_data["U"]), axis=1)
    if "U" in result.cell_data:
        result.cell_data[VELOCITY_MAGNITUDE_FIELD] = np.linalg.norm(np.asarray(result.cell_data["U"]), axis=1)
    return result


def load_case_volume(run_dir: Path) -> pv.UnstructuredGrid | None:
    """Returns the case's internal (volumetric) mesh with a U_magnitude field added, at
    its last written time step, or None if it can't be read (missing mesh, no U field, an
    OpenFOAM version the installed reader doesn't support). Only affects the optional
    volume-field preview; the solved case on disk is unaffected either way."""
    if not (run_dir / "constant" / "polyMesh").exists():
        return None
    foam_file = run_dir / VOLUME_FOAM_FILENAME
    if not foam_file.exists():
        foam_file.touch()
    try:
        reader = pv.OpenFOAMReader(str(foam_file))
        if reader.time_values:
            reader.set_active_time_value(reader.time_values[-1])
        blocks = reader.read()
        internal = blocks["internalMesh"]
    except (KeyError, RuntimeError, OSError, ValueError):
        return None
    if internal is None or _field_array(internal, "U") is None:
        return None
    return _with_velocity_magnitude(internal)


def velocity_magnitude_slice(volume: pv.UnstructuredGrid, normal: str = "y") -> pv.PolyData:
    """A single planar cutting-plane slice through the volume, colored by velocity
    magnitude -- the closest OpenFOAM-native analog of a 2D CFD contour plot."""
    return volume.slice(normal=normal)


def flow_path_traces(
    volume: pv.UnstructuredGrid, source_center: tuple[float, float, float], source_radius: float, n_points: int = 40,
) -> pv.PolyData:
    """Flow-path traces (curves tangent to the velocity field) seeded from a small disc."""
    return volume.streamlines(  # noqa: 4 (pyvista's own filter name, not our prose)
        vectors="U", source_center=source_center, source_radius=source_radius, n_points=n_points
    )
