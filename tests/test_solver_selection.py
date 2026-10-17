"""Mach-regime -> OpenFOAM solver selection."""
from __future__ import annotations

import pytest

from rocketcfd.solver_selection import (
    HARD_MACH_LIMIT,
    INCOMPRESSIBLE,
    SUBSONIC_COMPRESSIBLE,
    SUPERSONIC,
    TRANSONIC,
    MachOutOfRangeError,
    select_solver,
)


def test_low_mach_selects_incompressible_simplefoam() -> None:
    selection = select_solver(0.1)
    assert selection.regime == INCOMPRESSIBLE
    assert selection.application == "simpleFoam"
    assert not selection.compressible
    assert selection.warnings == []


def test_subsonic_compressible_selects_rhosimplefoam() -> None:
    selection = select_solver(0.5)
    assert selection.regime == SUBSONIC_COMPRESSIBLE
    assert selection.application == "rhoSimpleFoam"
    assert selection.compressible
    assert selection.steady


def test_transonic_selects_transient_rhopimplefoam_with_warning() -> None:
    selection = select_solver(1.0)
    assert selection.regime == TRANSONIC
    assert selection.application == "rhoPimpleFoam"
    assert not selection.steady
    assert selection.warnings


def test_supersonic_selects_rhocentralfoam_with_warning() -> None:
    selection = select_solver(2.5)
    assert selection.regime == SUPERSONIC
    assert selection.application == "rhoCentralFoam"
    assert not selection.steady
    assert selection.warnings


def test_mach_above_ceiling_raises() -> None:
    with pytest.raises(MachOutOfRangeError):
        select_solver(4.0, mach_ceiling=3.0)


def test_ceiling_above_hard_limit_raises() -> None:
    with pytest.raises(MachOutOfRangeError):
        select_solver(1.0, mach_ceiling=HARD_MACH_LIMIT + 1.0)


def test_negative_mach_raises() -> None:
    with pytest.raises(MachOutOfRangeError):
        select_solver(-0.1)


def test_default_ceiling_allows_mach_three() -> None:
    selection = select_solver(3.0)
    assert selection.regime == SUPERSONIC
