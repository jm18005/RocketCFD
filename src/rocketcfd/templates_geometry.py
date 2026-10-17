"""Parametric rocket-part geometry generators (body tube, nosecone, fin, boattail) for
quick comparative studies, without needing an external CAD tool for a first pass.

Parts are assembled by concatenation, not a boolean union, so seams between parts are
open surfaces rather than a single watertight solid; run the result through
geometry.ensure_watertight (as the geometry-load path already does) before meshing.
"""
from __future__ import annotations

import numpy as np
import trimesh

DEFAULT_SEGMENTS = 48

NOSECONE_CONIC = "conic"
NOSECONE_OGIVE = "ogive"
NOSECONE_VON_KARMAN = "von_karman"
NOSECONE_SHAPES = (NOSECONE_CONIC, NOSECONE_OGIVE, NOSECONE_VON_KARMAN)


def _surface_of_revolution(axial: np.ndarray, radius: np.ndarray, segments: int = DEFAULT_SEGMENTS) -> trimesh.Trimesh:
    """Revolves a radius(axial) profile about the +X axis into a triangulated shell."""
    theta = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    cos_t, sin_t = np.cos(theta), np.sin(theta)

    n_rings = len(axial)
    vertices = np.zeros((n_rings * segments, 3))
    for i in range(n_rings):
        vertices[i * segments : (i + 1) * segments, 0] = axial[i]
        vertices[i * segments : (i + 1) * segments, 1] = radius[i] * cos_t
        vertices[i * segments : (i + 1) * segments, 2] = radius[i] * sin_t

    faces = []
    for i in range(n_rings - 1):
        for j in range(segments):
            j_next = (j + 1) % segments
            a = i * segments + j
            b = i * segments + j_next
            c = (i + 1) * segments + j_next
            d = (i + 1) * segments + j
            if radius[i] > 1e-9:
                faces.append((a, b, c))
            if radius[i + 1] > 1e-9:
                faces.append((a, c, d))
    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces, dtype=np.int64), process=True)


def body_tube(length: float, diameter: float, segments: int = DEFAULT_SEGMENTS) -> trimesh.Trimesh:
    radius = diameter / 2.0
    axial = np.array([0.0, length])
    return _surface_of_revolution(axial, np.array([radius, radius]), segments)


def boattail(length: float, forward_diameter: float, aft_diameter: float, segments: int = DEFAULT_SEGMENTS) -> trimesh.Trimesh:
    axial = np.array([0.0, length])
    radius = np.array([forward_diameter / 2.0, aft_diameter / 2.0])
    return _surface_of_revolution(axial, radius, segments)


def _nosecone_profile(length: float, base_radius: float, shape: str, n_points: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.linspace(0.0, length, n_points)
    if shape == NOSECONE_CONIC:
        r = base_radius * (x / length)
    elif shape == NOSECONE_OGIVE:
        # Tangent-ogive profile: R = rho*sin(theta_at_x); rho is the ogive radius solved
        # from base_radius/length so the profile meets the base radius at x=length.
        rho = (base_radius**2 + length**2) / (2.0 * base_radius)
        r = np.sqrt(np.maximum(rho**2 - (length - x) ** 2, 0.0)) + base_radius - rho
    elif shape == NOSECONE_VON_KARMAN:
        theta = np.arccos(1.0 - 2.0 * x / length)
        r = base_radius * np.sqrt((theta - np.sin(2.0 * theta) / 2.0) / np.pi)
    else:
        raise ValueError(f"Unknown nosecone shape '{shape}'; choose one of {NOSECONE_SHAPES}")
    r = np.clip(r, 0.0, base_radius)
    r[0] = 0.0
    return x, r


def nosecone(length: float, base_diameter: float, shape: str = NOSECONE_OGIVE, segments: int = DEFAULT_SEGMENTS, n_points: int = 40) -> trimesh.Trimesh:
    axial, radius = _nosecone_profile(length, base_diameter / 2.0, shape, n_points)
    return _surface_of_revolution(axial, radius, segments)


def trapezoidal_fin(root_chord: float, tip_chord: float, span: float, sweep_distance: float, thickness: float) -> trimesh.Trimesh:
    """A flat-plate fin of uniform thickness: root chord along the body's surface at
    x=0..root_chord, tip chord offset by sweep_distance and raised by span."""
    outline = np.array(
        [
            [0.0, 0.0],
            [root_chord, 0.0],
            [sweep_distance + tip_chord, span],
            [sweep_distance, span],
        ]
    )
    polygon_mesh = trimesh.creation.extrude_polygon(_to_shapely_polygon(outline), height=thickness)
    polygon_mesh.apply_translation([0.0, 0.0, -thickness / 2.0])
    return polygon_mesh


def _to_shapely_polygon(points: np.ndarray) -> object:
    from shapely.geometry import Polygon  # noqa: 13 (trimesh's own extrude_polygon dependency, imported lazily to match it)

    return Polygon(points)


REGION_NOSECONE = "nosecone"
REGION_BODY_TUBE = "body_tube"
REGION_FIN = "fin"
REGION_BOATTAIL = "boattail"


def _assemble_parts(
    nosecone_mesh: trimesh.Trimesh,
    body_tube_mesh: trimesh.Trimesh,
    fins: list[trimesh.Trimesh] | None,
    boattail_mesh: trimesh.Trimesh | None,
) -> list[tuple[trimesh.Trimesh, str]]:
    """Places nosecone at x=0, body tube immediately aft of it, fins at the aft end of the
    body tube (evenly spaced about the axis), and an optional boattail aft of the body
    tube. Returns each placed part paired with its region name, in concatenation order."""
    nose_length = float(nosecone_mesh.bounds[1][0])
    parts: list[tuple[trimesh.Trimesh, str]] = [(nosecone_mesh, REGION_NOSECONE)]

    body = body_tube_mesh.copy()
    body.apply_translation([nose_length, 0.0, 0.0])
    parts.append((body, REGION_BODY_TUBE))
    body_length = float(body_tube_mesh.bounds[1][0])

    if fins:
        fin_x = nose_length + body_length - float(fins[0].bounds[1][0])
        n_fins = len(fins)
        for i, fin in enumerate(fins):
            angle = 2.0 * np.pi * i / n_fins
            rotated = fin.copy()
            rotated.apply_transform(trimesh.transformations.rotation_matrix(angle, [1.0, 0.0, 0.0]))
            rotated.apply_translation([fin_x, 0.0, 0.0])
            parts.append((rotated, REGION_FIN))

    if boattail_mesh is not None:
        tail = boattail_mesh.copy()
        tail.apply_translation([nose_length + body_length, 0.0, 0.0])
        parts.append((tail, REGION_BOATTAIL))

    return parts


def assemble_rocket(
    nosecone_mesh: trimesh.Trimesh,
    body_tube_mesh: trimesh.Trimesh,
    fins: list[trimesh.Trimesh] | None = None,
    boattail_mesh: trimesh.Trimesh | None = None,
) -> trimesh.Trimesh:
    """Returns the concatenated (non-boolean-unioned) rocket assembly, with no per-part
    region labels; see assemble_rocket_labeled for the labeled variant used by
    feature-specific mesh refinement."""
    parts = [mesh for mesh, _region in _assemble_parts(nosecone_mesh, body_tube_mesh, fins, boattail_mesh)]
    return trimesh.util.concatenate(parts)


def assemble_rocket_labeled(
    nosecone_mesh: trimesh.Trimesh,
    body_tube_mesh: trimesh.Trimesh,
    fins: list[trimesh.Trimesh] | None = None,
    boattail_mesh: trimesh.Trimesh | None = None,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Same placement as assemble_rocket, but also returns a per-face region-name array
    (REGION_NOSECONE/REGION_BODY_TUBE/REGION_FIN/REGION_BOATTAIL) so snappyHexMesh can
    apply a different refinement level to each part (see
    openfoam.templates.snappy_hex_mesh_dict's feature_refinement argument)."""
    parts = _assemble_parts(nosecone_mesh, body_tube_mesh, fins, boattail_mesh)
    face_regions = np.concatenate([np.full(len(mesh.faces), region, dtype=object) for mesh, region in parts])
    combined = trimesh.util.concatenate([mesh for mesh, _region in parts])
    return combined, face_regions
