"""User-configurable meshing/solver/execution settings for an OpenFOAM automation run."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from rocketcfd.solver_selection import DEFAULT_MACH_CEILING

TURBULENCE_MODELS = ("kOmegaSST", "SpalartAllmaras")

EXECUTION_NATIVE_LINUX = "native_linux"
EXECUTION_WSL = "wsl"
EXECUTION_TACC = "tacc"
EXECUTION_MODES = (EXECUTION_WSL, EXECUTION_NATIVE_LINUX, EXECUTION_TACC)

MESH_PRESET_COARSE = "Coarse"
MESH_PRESET_MEDIUM = "Medium"
MESH_PRESET_FINE = "Fine"
MESH_PRESET_CUSTOM = "Custom"
MESH_PRESET_NAMES = (MESH_PRESET_COARSE, MESH_PRESET_MEDIUM, MESH_PRESET_FINE)

DOMAIN_AXES = ("x", "y", "z")
DOMAIN_PLANE_SIDES = ("min", "max")


@dataclass(frozen=True)
class GroundPlane:
    """A no-slip wall patch replacing one face of the domain box, approximating a
    stationary ground/pad. axis picks which world axis is "down"; side picks which
    face of the domain box (its low or high bound on that axis) becomes the wall."""

    axis: str = "z"
    side: str = "min"


@dataclass(frozen=True)
class SymmetryPlane:
    """A symmetryPlane patch cutting the domain at `offset` along `axis`: only the
    axis >= offset half is meshed and mirrored, halving cell count for a body symmetric
    about that plane. Combine two (on different axes) to mesh a quarter-body."""

    axis: str
    offset: float


def validate_domain_planes(ground_plane: GroundPlane | None, symmetry_planes: tuple[SymmetryPlane, ...]) -> None:
    if len(symmetry_planes) > 2:
        raise ValueError("at most 2 symmetry planes are supported (one per axis, for quarter-body meshing)")
    symmetry_axes = [plane.axis for plane in symmetry_planes]
    if len(symmetry_axes) != len(set(symmetry_axes)):
        raise ValueError("symmetry planes must each use a different axis")
    for axis in symmetry_axes + ([ground_plane.axis] if ground_plane is not None else []):
        if axis not in DOMAIN_AXES:
            raise ValueError(f"unknown axis '{axis}'; expected one of {DOMAIN_AXES}")
    if ground_plane is not None:
        if ground_plane.side not in DOMAIN_PLANE_SIDES:
            raise ValueError(f"unknown ground plane side '{ground_plane.side}'; expected one of {DOMAIN_PLANE_SIDES}")
        if ground_plane.axis in symmetry_axes:
            raise ValueError("the ground plane and a symmetry plane cannot use the same axis")


@dataclass
class MeshSettings:
    """background_cell_count is deliberately small (a coarse blockMesh background, not
    the final surface resolution): snappyHexMesh's surface_refinement levels each halve
    the local cell size via octree splitting near the body, so the actual near-surface
    cell size ends up background_cell_size / 2**surface_refinement_max."""

    upstream_lengths: float = 5.0
    downstream_lengths: float = 10.0
    side_lengths: float = 5.0
    top_lengths: float = 5.0
    background_cell_count: int = 4
    surface_refinement_min: int = 2
    surface_refinement_max: int = 4
    n_boundary_layers: int = 5
    boundary_layer_expansion_ratio: float = 1.2
    final_layer_thickness_ratio: float = 0.3
    use_target_y_plus: bool = True
    target_y_plus: float = 1.0
    feature_refinement_levels: dict[str, tuple[int, int]] = field(default_factory=dict)
    max_non_orthogonality: float = 65.0
    max_skewness: float = 4.0
    require_mesh_quality_pass: bool = True


MESH_PRESETS: dict[str, MeshSettings] = {
    MESH_PRESET_COARSE: MeshSettings(
        background_cell_count=3, surface_refinement_min=1, surface_refinement_max=2, n_boundary_layers=3,
        target_y_plus=30.0,
    ),
    MESH_PRESET_MEDIUM: MeshSettings(
        background_cell_count=4, surface_refinement_min=2, surface_refinement_max=4, n_boundary_layers=5,
        target_y_plus=1.0,
    ),
    MESH_PRESET_FINE: MeshSettings(
        background_cell_count=6, surface_refinement_min=3, surface_refinement_max=6, n_boundary_layers=8,
        target_y_plus=0.5,
    ),
}


def mesh_settings_for_preset(preset: str) -> MeshSettings:
    """Returns a copy of the named mesh-density preset (coarse/medium/fine): background
    cell count, surface refinement levels, boundary layer count, and target y+ scaled
    together, so switching density does not leave e.g. a fine surface mesh with a coarse
    boundary layer."""
    if preset not in MESH_PRESETS:
        raise ValueError(f"Unknown mesh preset '{preset}'; choose one of {MESH_PRESET_NAMES}")
    return replace(MESH_PRESETS[preset], feature_refinement_levels=dict(MESH_PRESETS[preset].feature_refinement_levels))


@dataclass
class SolverSettings:
    turbulence_model: str = "kOmegaSST"
    turbulence_intensity: float = 0.05
    max_iterations: int = 1000
    convergence_residual: float = 1e-4
    n_processors: int = field(default_factory=lambda: max(1, os.cpu_count() or 1))
    mach_ceiling: float = DEFAULT_MACH_CEILING


@dataclass
class WslSettings:
    """openfoam_bashrc left blank means auto-detect: a hardcoded version-specific default
    path (e.g. openfoam2312) breaks the moment a WSL install is a different version, so an
    empty string instead asks runner.find_openfoam_bashrc to search common install
    locations at run time."""

    distro: str = ""
    openfoam_bashrc: str = ""
    case_root: Path = field(default_factory=lambda: Path.home() / "rocketcfd-openfoam-cases")


@dataclass
class NativeLinuxSettings:
    """Same role as WslSettings but for running directly on a Linux host (no wsl.exe hop)."""

    openfoam_bashrc: str = ""
    case_root: Path = field(default_factory=lambda: Path.home() / "rocketcfd-openfoam-cases")
