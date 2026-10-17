"""pyvista helpers for rendering the panel mesh and result overlays."""
from __future__ import annotations

import numpy as np
import pyvista as pv

from rocketcfd.flow import wind_unit
from rocketcfd.geometry import PanelMesh
from rocketcfd.openfoam.settings import GroundPlane, SymmetryPlane

_AXIS_UNIT_VECTORS = {"x": np.array([1.0, 0.0, 0.0]), "y": np.array([0.0, 1.0, 0.0]), "z": np.array([0.0, 0.0, 1.0])}


def panel_mesh_to_polydata(panel_mesh: PanelMesh) -> pv.PolyData:
    n_faces = panel_mesh.faces.shape[0]
    padded = np.hstack([np.full((n_faces, 1), 3, dtype=np.int64), panel_mesh.faces])
    return pv.PolyData(panel_mesh.vertices, padded.ravel())


def _robust_clim(scalars: np.ndarray, zero_centered: bool = False) -> tuple[float, float]:
    """1st/99th-percentile color range instead of raw min/max, so a handful of outlier
    panel values cannot saturate the entire body to a single color. zero_centered makes
    the range symmetric about 0 (for signed fields like Cp)."""
    lo, hi = np.percentile(scalars, [1.0, 99.0])
    if zero_centered:
        bound = max(abs(lo), abs(hi), 1e-12)
        return -bound, bound
    if hi - lo < 1e-12:
        lo, hi = float(np.min(scalars)), float(np.max(scalars))
    if hi - lo < 1e-12:
        hi = lo + 1.0
    return float(lo), float(hi)


def render_scalar_field(
    plotter: pv.Plotter,
    polydata: pv.PolyData,
    scalars: np.ndarray,
    scalar_name: str,
    cmap: str | None = None,
    opacity: float = 1.0,
    zero_centered: bool = False,
) -> None:
    plotter.clear_actors()
    mesh = polydata.copy()
    if len(scalars) == mesh.n_points and len(scalars) != mesh.n_cells:
        mesh.point_data[scalar_name] = scalars
    else:
        mesh.cell_data[scalar_name] = scalars
    plotter.add_mesh(
        mesh,
        scalars=scalar_name,
        cmap=cmap or ("coolwarm" if zero_centered else "turbo"),
        clim=_robust_clim(scalars, zero_centered),
        show_edges=False,
        name="panel_mesh",
        opacity=opacity,
    )


_AXIS_DIRECTIONS = {
    "X": (np.array([1.0, 0.0, 0.0]), "red"),
    "Y": (np.array([0.0, 1.0, 0.0]), "green"),
    "Z": (np.array([0.0, 0.0, 1.0]), "blue"),
}


def add_axis_triad(plotter: pv.Plotter, axis_length: float, origin: np.ndarray | None = None) -> None:
    origin = np.zeros(3) if origin is None else origin
    for axis_name, (direction, color) in _AXIS_DIRECTIONS.items():
        arrow = pv.Arrow(start=origin, direction=direction, scale=axis_length)
        plotter.add_mesh(arrow, color=color, name=f"axis_{axis_name}")
        plotter.add_point_labels(
            [origin + direction * axis_length * 1.1], [axis_name], font_size=16, text_color=color, shape=None,
            name=f"axis_label_{axis_name}",
        )


_BBOX_AXES = (
    ("Length", np.array([1.0, 0.0, 0.0]), "red"),
    ("Width", np.array([0.0, 1.0, 0.0]), "green"),
    ("Height", np.array([0.0, 0.0, 1.0]), "blue"),
)


def add_bounding_box(plotter: pv.Plotter, mesh_polydata: pv.PolyData) -> None:
    bounds = mesh_polydata.bounds
    low = np.array([bounds[0], bounds[2], bounds[4]])
    high = np.array([bounds[1], bounds[3], bounds[5]])
    size = high - low

    box = pv.Box(bounds=bounds)
    plotter.add_mesh(box, color="cyan", style="wireframe", line_width=2, name="bbox")

    for axis_label, direction, color in _BBOX_AXES:
        extent = float(np.dot(size, direction))
        arrow = pv.Arrow(start=low, direction=direction, scale=max(extent, 1e-9))
        plotter.add_mesh(arrow, color=color, name=f"bbox_axis_{axis_label}")
        plotter.add_point_labels(
            [low + direction * extent * 1.1], [f"{axis_label}: {extent:.3g} m"], font_size=12, text_color=color,
            shape=None, name=f"bbox_label_{axis_label}",
        )


_DOMAIN_AXIS_SPANS = (
    ("X", np.array([1.0, 0.0, 0.0]), "Upstream+downstream span"),
    ("Y", np.array([0.0, 1.0, 0.0]), "Side-to-side span"),
    ("Z", np.array([0.0, 0.0, 1.0]), "Top span"),
)


_DOMAIN_AXIS_BOUND_INDEX = {"x": (0, 1), "y": (2, 3), "z": (4, 5)}


def _domain_bound(domain: tuple[float, float, float, float, float, float], axis: str, side: str) -> float:
    lo_index, hi_index = _DOMAIN_AXIS_BOUND_INDEX[axis]
    return domain[lo_index] if side == "min" else domain[hi_index]


def _axis_plane_patch(
    domain: tuple[float, float, float, float, float, float], axis: str, position: float
) -> tuple[tuple[float, float, float], np.ndarray, float, float]:
    """Center/normal/extents of a plane perpendicular to `axis` at `position`, spanning
    the domain's full extent along the other two axes."""
    xmin, xmax, ymin, ymax, zmin, zmax = domain
    spans = {"x": (xmin, xmax), "y": (ymin, ymax), "z": (zmin, zmax)}
    center = {"x": 0.5 * (xmin + xmax), "y": 0.5 * (ymin + ymax), "z": 0.5 * (zmin + zmax)}
    center[axis] = position
    other_axes = [a for a in ("x", "y", "z") if a != axis]
    i_size = spans[other_axes[0]][1] - spans[other_axes[0]][0]
    j_size = spans[other_axes[1]][1] - spans[other_axes[1]][0]
    return (center["x"], center["y"], center["z"]), _AXIS_UNIT_VECTORS[axis], i_size, j_size


def add_domain_box(
    plotter: pv.Plotter,
    domain: tuple[float, float, float, float, float, float],
    location_in_mesh: tuple[float, float, float] | None = None,
    ground_plane: GroundPlane | None = None,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
) -> None:
    xmin, xmax, ymin, ymax, zmin, zmax = domain
    low = np.array([xmin, ymin, zmin])
    high = np.array([xmax, ymax, zmax])
    size = high - low

    box = pv.Box(bounds=domain)
    plotter.add_mesh(box, color="orange", style="wireframe", line_width=2, opacity=0.5, name="domain_box")

    for key, direction, description in _DOMAIN_AXIS_SPANS:
        extent = float(np.dot(size, direction))
        plotter.add_point_labels(
            [low + direction * extent * 1.02], [f"{description}: {extent:.3g} m"], font_size=11, text_color="orange",
            shape=None, name=f"domain_label_{key}",
        )

    if ground_plane is not None:
        position = _domain_bound(domain, ground_plane.axis, ground_plane.side)
        center, direction, i_size, j_size = _axis_plane_patch(domain, ground_plane.axis, position)
        ground_patch = pv.Plane(center=center, direction=direction, i_size=i_size, j_size=j_size)
        plotter.add_mesh(ground_patch, color="saddlebrown", opacity=0.25, name="ground_patch")

    for index, plane in enumerate(symmetry_planes):
        position = _domain_bound(domain, plane.axis, "min")
        center, direction, i_size, j_size = _axis_plane_patch(domain, plane.axis, position)
        mirror_patch = pv.Plane(center=center, direction=direction, i_size=i_size, j_size=j_size)
        plotter.add_mesh(mirror_patch, color="deepskyblue", opacity=0.2, name=f"mirror_patch_{index}")

    if location_in_mesh is not None:
        radius = max(float(np.max(size)) * 0.01, 1e-6)
        marker = pv.Sphere(radius=radius, center=location_in_mesh)
        plotter.add_mesh(marker, color="lime", name="location_in_mesh")
        plotter.add_point_labels(
            [location_in_mesh], ["locationInMesh (snappyHexMesh seed point)"], font_size=11, text_color="lime",
            shape=None, name="location_in_mesh_label",
        )


def render_reference_scene(
    plotter: pv.Plotter,
    moment_ref: np.ndarray,
    mesh_polydata: pv.PolyData | None = None,
    direction_unit: np.ndarray | None = None,
    wind_speed: float = 0.0,
    wind_direction_deg: float = 0.0,
    wind_elevation_deg: float = 0.0,
    vehicle_speed: float = 0.0,
) -> None:
    """Draws the STL (if loaded), the X/Y/Z axis triad, the vehicle's own flow-direction
    arrow, and (if wind_speed > 0) the ambient wind-direction arrow and their vector sum
    (the "total flow direction" the vehicle actually experiences), all anchored at the
    moment reference point."""
    plotter.clear_actors()
    bounds = mesh_polydata.bounds if mesh_polydata is not None else (-1.0, 1.0, -1.0, 1.0, -1.0, 1.0)
    span = max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4], 1.0)
    axis_length = span * 0.6

    if mesh_polydata is not None:
        plotter.add_mesh(mesh_polydata, color="lightgray", opacity=0.3, show_edges=False, name="context_mesh")

    ref_marker = pv.Sphere(radius=axis_length * 0.03, center=moment_ref)
    plotter.add_mesh(ref_marker, color="yellow", name="ref_marker")
    label = f"Moment ref ({moment_ref[0]:.3g}, {moment_ref[1]:.3g}, {moment_ref[2]:.3g})"
    plotter.add_point_labels([moment_ref], [label], font_size=12, shape=None, name="ref_label")

    add_axis_triad(plotter, axis_length, moment_ref)

    if direction_unit is not None:
        _add_labeled_vector(plotter, moment_ref, direction_unit, axis_length * 1.3, "magenta", "Flow", "flow")

    if wind_speed > 1e-9:
        wind_direction_unit = wind_unit(wind_direction_deg, wind_elevation_deg)
        _add_labeled_vector(plotter, moment_ref, wind_direction_unit, axis_length * 1.1, "cyan", "Wind", "wind")
        if direction_unit is not None:
            total_vector = vehicle_speed * direction_unit + wind_speed * wind_direction_unit
            total_norm = np.linalg.norm(total_vector)
            if total_norm > 1e-9:
                _add_labeled_vector(
                    plotter, moment_ref, total_vector / total_norm, axis_length * 1.5, "lime", "Total flow", "total_flow"
                )

    plotter.reset_camera()


def _add_labeled_vector(
    plotter: pv.Plotter, origin: np.ndarray, unit_vector: np.ndarray, length: float, color: str, label: str, name: str
) -> None:
    arrow = pv.Arrow(start=origin, direction=unit_vector, scale=length)
    plotter.add_mesh(arrow, color=color, name=f"{name}_arrow")
    plotter.add_point_labels(
        [origin + unit_vector * length], [label], font_size=14, text_color=color, shape=None, name=f"{name}_label"
    )
