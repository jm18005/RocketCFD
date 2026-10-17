"""Analytic/tabulated validation reference values."""
from __future__ import annotations

import pytest

from rocketcfd.validation.reference_data import flat_plate_cf, slender_cone_wave_drag_cd, sphere_cd_reference


def test_flat_plate_cf_laminar_matches_blasius() -> None:
    reynolds = 1e5
    assert flat_plate_cf(reynolds) == pytest.approx(1.328 / reynolds**0.5, rel=1e-9)


def test_flat_plate_cf_turbulent_matches_correlation() -> None:
    reynolds = 1e7
    assert flat_plate_cf(reynolds) == pytest.approx(0.074 / reynolds**0.2, rel=1e-9)


def test_flat_plate_cf_requires_positive_reynolds() -> None:
    with pytest.raises(ValueError):
        flat_plate_cf(0.0)


def test_sphere_cd_subcritical_plateau() -> None:
    cd = sphere_cd_reference(1e4)
    assert 0.3 < cd < 0.6


def test_sphere_cd_drag_crisis_drop() -> None:
    subcritical = sphere_cd_reference(1e5)
    supercritical = sphere_cd_reference(4e5)
    assert supercritical < subcritical


def test_cone_wave_drag_requires_supersonic() -> None:
    with pytest.raises(ValueError):
        slender_cone_wave_drag_cd(10.0, 0.8)


def test_cone_wave_drag_increases_with_half_angle() -> None:
    narrow = slender_cone_wave_drag_cd(5.0, 2.0)
    wide = slender_cone_wave_drag_cd(15.0, 2.0)
    assert wide > narrow
