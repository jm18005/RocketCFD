"""3D model loading (mesh and CAD formats), watertight repair, and panel-mesh extraction."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymeshfix
import trimesh

MESH_EXTENSIONS = {".stl", ".obj", ".ply"}
BREP_EXTENSIONS = {".step", ".stp", ".iges", ".igs"}

CAD_INSTALL_HINT = "STEP/IGES support requires the optional CAD backend. Install it with: pip install -e .[cad]"
MANUAL_REPAIR_HINT = (
    "Automatic repair could not make this mesh watertight. Fix it manually in a mesh/CAD "
    "tool (fill holes, remove duplicate/degenerate faces, unify normals) and reload it."
)


class GeometryNotWatertightError(ValueError):
    """Raised when a loaded mesh is not watertight and automatic repair failed."""


@dataclass
class RepairReport:
    was_watertight: bool
    is_watertight: bool
    method: str


@dataclass
class PanelMesh:
    vertices: np.ndarray
    faces: np.ndarray
    centroids: np.ndarray
    normals: np.ndarray
    areas: np.ndarray
    face_regions: np.ndarray | None = None

    @property
    def panel_count(self) -> int:
        return int(self.faces.shape[0])

    def centroid(self) -> np.ndarray:
        return np.average(self.centroids, axis=0, weights=self.areas)

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        low = self.vertices.min(axis=0)
        high = self.vertices.max(axis=0)
        return (float(low[0]), float(high[0]), float(low[1]), float(high[1]), float(low[2]), float(high[2]))


def brep_backend_available() -> bool:
    """Cheap probe for the optional CAD backend; never raises."""
    try:
        return importlib.util.find_spec("OCP") is not None
    except (ImportError, ValueError):
        return False


def load_model(path: str | Path) -> trimesh.Trimesh:
    """Loads a triangulated mesh (STL/OBJ/PLY) directly, or tessellates a STEP/IGES
    BREP model into a mesh via the optional OCP backend."""
    ext = Path(path).suffix.lower()
    if ext in BREP_EXTENSIONS:
        if not brep_backend_available():
            raise RuntimeError(CAD_INSTALL_HINT)
        from rocketcfd.brep_backend import brep_load, brep_tessellate  # noqa: 13 (optional CAD backend, see brep_backend module docstring)
        shape = brep_load(str(path))
        vertices, faces = brep_tessellate(shape)
        if len(faces) == 0:
            raise ValueError(f"{path} tessellated to an empty mesh")
        return trimesh.Trimesh(vertices=vertices, faces=faces)
    if ext not in MESH_EXTENSIONS:
        raise ValueError(f"Unsupported 3D model format: {ext}")
    mesh = trimesh.load(str(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"{path} did not load as a single triangular mesh")
    return mesh


def ensure_watertight(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, RepairReport]:
    """Attempts automatic repair; raises GeometryNotWatertightError if the mesh is still
    not watertight afterward, so callers surface a manual-fix message instead of running
    a case on leaky geometry."""
    was_watertight = bool(mesh.is_watertight)
    if was_watertight:
        return mesh, RepairReport(True, True, "none")

    repaired = mesh.copy()
    trimesh.repair.fix_winding(repaired)
    trimesh.repair.fix_normals(repaired)
    trimesh.repair.fill_holes(repaired)
    if repaired.is_watertight:
        return repaired, RepairReport(False, True, "trimesh_fill_holes")

    fixed_vertices, fixed_faces = _pymeshfix_repair(mesh.vertices, mesh.faces)
    repaired = trimesh.Trimesh(vertices=fixed_vertices, faces=fixed_faces, process=True)
    if not repaired.is_watertight:
        raise GeometryNotWatertightError(MANUAL_REPAIR_HINT)
    return repaired, RepairReport(False, True, "pymeshfix")


def _pymeshfix_repair(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    fixer = pymeshfix.MeshFix(vertices, faces)
    fixer.repair()
    return fixer.points, fixer.faces


def scale_mesh(mesh: trimesh.Trimesh, factor: float) -> trimesh.Trimesh:
    scaled = mesh.copy()
    scaled.apply_scale(factor)
    return scaled


def rotate_mesh(mesh: trimesh.Trimesh, angles_deg: tuple[float, float, float]) -> trimesh.Trimesh:
    """Rotates the mesh about the origin by the given X, then Y, then Z angles (degrees).
    This is the single point where a user-chosen orientation is baked into the geometry
    that both the 3D view and the CFD solve consume."""
    rotated = mesh.copy()
    rx, ry, rz = (np.radians(angle) for angle in angles_deg)
    matrix = trimesh.transformations.euler_matrix(rx, ry, rz, axes="sxyz")
    rotated.apply_transform(matrix)
    return rotated


def to_panel_mesh(mesh: trimesh.Trimesh, face_regions: np.ndarray | None = None) -> PanelMesh:
    return PanelMesh(
        vertices=np.asarray(mesh.vertices, dtype=np.float64),
        faces=np.asarray(mesh.faces, dtype=np.int64),
        centroids=np.asarray(mesh.triangles_center, dtype=np.float64),
        normals=np.asarray(mesh.face_normals, dtype=np.float64),
        areas=np.asarray(mesh.area_faces, dtype=np.float64),
        face_regions=face_regions,
    )


def frontal_area(panel_mesh: PanelMesh, direction_unit: np.ndarray) -> float:
    """Projected (silhouette) area of the mesh as seen looking along direction_unit,
    used as the default aerodynamic reference area."""
    cos_impact = panel_mesh.normals @ direction_unit
    projected = np.clip(-cos_impact, 0.0, 1.0) * panel_mesh.areas
    return float(projected.sum())
