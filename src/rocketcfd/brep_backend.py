"""OpenCASCADE (OCP) backend for reading STEP/IGES CAD geometry into a triangle mesh.

Every OCP import lives inside a function body, never at module scope, so a
broken or missing install of the optional `cadquery-ocp` package can never
prevent `rocketcfd.geometry` (and therefore the rest of the app) from
importing successfully.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def brep_load(path: str) -> Any:
    """Read a STEP or IGES file and return its top-level TopoDS_Shape."""
    from OCP.IFSelect import IFSelect_RetDone  # noqa: 13 (optional CAD backend, see module docstring)

    lower = path.lower()
    if lower.endswith(".iges") or lower.endswith(".igs"):
        from OCP.IGESControl import IGESControl_Reader  # noqa: 13 (optional CAD backend, see module docstring)
        reader = IGESControl_Reader()
    else:
        from OCP.STEPControl import STEPControl_Reader  # noqa: 13 (optional CAD backend, see module docstring)
        reader = STEPControl_Reader()

    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise ValueError(f"Could not read CAD file: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def brep_tessellate(shape: Any, linear_deflection: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Tessellate *shape* into (vertices, faces) float64/int64 numpy arrays."""
    from OCP.BRep import BRep_Tool  # noqa: 13 (optional CAD backend, see module docstring)
    from OCP.BRepMesh import BRepMesh_IncrementalMesh  # noqa: 13 (optional CAD backend, see module docstring)
    from OCP.TopAbs import TopAbs_FACE  # noqa: 13 (optional CAD backend, see module docstring)
    from OCP.TopExp import TopExp_Explorer  # noqa: 13 (optional CAD backend, see module docstring)
    from OCP.TopLoc import TopLoc_Location  # noqa: 13 (optional CAD backend, see module docstring)
    from OCP.TopoDS import TopoDS  # noqa: 13 (optional CAD backend, see module docstring)

    BRepMesh_IncrementalMesh(shape, linear_deflection)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, loc)
        if triangulation is not None:
            offset = len(verts)
            trsf = loc.Transformation()
            for i in range(1, triangulation.NbNodes() + 1):
                p = triangulation.Node(i).Transformed(trsf)
                verts.append((p.X(), p.Y(), p.Z()))
            for i in range(1, triangulation.NbTriangles() + 1):
                tri = triangulation.Triangle(i)
                a, b, c = tri.Get()
                faces.append((offset + a - 1, offset + b - 1, offset + c - 1))
        explorer.Next()
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)
