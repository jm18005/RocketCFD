"""Picks an OpenFOAM solver/regime from a flight Mach number.

Rockets spend most of an ascent below Mach 3, so that is the safe default
ceiling: transonic/supersonic automation carries lower confidence than the
incompressible/subsonic-compressible path below it. SolverSettings.mach_ceiling
is a user-adjustable setting, capped at HARD_MACH_LIMIT, above which
calorically-perfect-air and this tool's fixed scheme/BC set stop being a
reasonable approximation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_MACH_CEILING = 3.0
HARD_MACH_LIMIT = 8.0

INCOMPRESSIBLE = "incompressible"
SUBSONIC_COMPRESSIBLE = "subsonic_compressible"
TRANSONIC = "transonic"
SUPERSONIC = "supersonic"

_INCOMPRESSIBLE_CEILING = 0.3
_SUBSONIC_COMPRESSIBLE_CEILING = 0.8
_TRANSONIC_CEILING = 1.2


class MachOutOfRangeError(ValueError):
    """Raised when the requested Mach number exceeds the configured ceiling."""


@dataclass
class SolverSelection:
    regime: str
    application: str
    compressible: bool
    steady: bool
    warnings: list[str] = field(default_factory=list)


def select_solver(mach: float, mach_ceiling: float = DEFAULT_MACH_CEILING) -> SolverSelection:
    """Classifies *mach* into a flow regime and the OpenFOAM solver that automates it.

    mach_ceiling is the maximum Mach number this run is allowed to reach (a user-facing
    advanced setting); raise MachOutOfRangeError above it, and above HARD_MACH_LIMIT
    regardless of the configured ceiling.
    """
    if mach_ceiling > HARD_MACH_LIMIT:
        raise MachOutOfRangeError(
            f"Mach ceiling {mach_ceiling:g} exceeds the hard limit of {HARD_MACH_LIMIT:g}: "
            "above this, real-gas/dissociation effects make the calorically-perfect-air "
            "model this tool writes unreliable."
        )
    if mach < 0.0:
        raise MachOutOfRangeError(f"Mach number must be non-negative, got {mach:g}.")
    if mach > mach_ceiling:
        raise MachOutOfRangeError(
            f"Mach {mach:g} exceeds the configured ceiling of {mach_ceiling:g}. Raise the "
            "Mach ceiling in advanced solver settings to allow it."
        )

    if mach < _INCOMPRESSIBLE_CEILING:
        return SolverSelection(INCOMPRESSIBLE, "simpleFoam", compressible=False, steady=True)
    if mach < _SUBSONIC_COMPRESSIBLE_CEILING:
        return SolverSelection(SUBSONIC_COMPRESSIBLE, "rhoSimpleFoam", compressible=True, steady=True)
    if mach < _TRANSONIC_CEILING:
        return SolverSelection(
            TRANSONIC,
            "rhoPimpleFoam",
            compressible=True,
            steady=False,
            warnings=[
                "Transonic flow (0.8 <= M < 1.2) has unsteady shock/boundary-layer "
                "interactions that steady solvers do not capture reliably; running "
                "transient rhoPimpleFoam instead of a steady solver, and review results "
                "manually before trusting them."
            ],
        )
    return SolverSelection(
        SUPERSONIC,
        "rhoCentralFoam",
        compressible=True,
        steady=False,
        warnings=[
            "Supersonic automation uses fixed upwind-biased schemes for robustness; mesh "
            "resolution around expected shocks/expansion fans is not adapted automatically "
            "and should be checked in the 3D view before relying on the results."
        ],
    )
