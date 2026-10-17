"""Loads a meshed OpenFOAM case's boundary surface -- the actual snappyHexMesh-generated
cells on the body patch -- for 3D preview, via pyvista's OpenFOAM reader. Distinct from
the smooth CAD-derived panel_mesh preview shown before meshing (viewport.py)."""
from __future__ import annotations

from pathlib import Path

import pyvista as pv

PREVIEW_FOAM_FILENAME = "preview.foam"


def load_mesh_boundary_surface(mesh_dir: Path, patch_name: str = "body") -> pv.PolyData | None:
    """Returns the meshed body patch as a surface with its real cell faceting, or None if
    no mesh exists yet or the installed OpenFOAM/pyvista reader can't read it (this only
    affects the optional 3D preview; the mesh on disk is unaffected either way)."""
    if not (mesh_dir / "constant" / "polyMesh").exists():
        return None

    foam_file = mesh_dir / PREVIEW_FOAM_FILENAME
    if not foam_file.exists():
        foam_file.touch()

    try:
        reader = pv.OpenFOAMReader(str(foam_file))
        reader.disable_all_patch_arrays()
        reader.enable_patch_array(f"patch/{patch_name}")
        if reader.time_values:
            reader.set_active_time_value(reader.time_values[-1])
        blocks = reader.read()
        surface = blocks["boundary"][patch_name]
    except (KeyError, RuntimeError, OSError, ValueError):
        return None
    if surface is None:
        return None
    return surface.extract_surface(algorithm="dataset_surface")
