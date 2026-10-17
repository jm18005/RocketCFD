"""US Standard Atmosphere sanity checks against well-known reference values."""
from __future__ import annotations

from rocketcfd.atmosphere import us_standard_atmosphere


def test_sea_level_matches_standard_constants() -> None:
    state = us_standard_atmosphere(0.0)
    assert abs(state.temperature - 288.15) < 1e-6
    assert abs(state.pressure - 101325.0) < 1e-6
    assert abs(state.density - 1.225) < 1e-3
    assert not state.approximate


def test_11km_tropopause_temperature() -> None:
    state = us_standard_atmosphere(11000.0)
    assert abs(state.temperature - 216.65) < 1e-6


def test_50000ft_within_supported_proposal_range() -> None:
    altitude_m = 50000.0 * 0.3048
    state = us_standard_atmosphere(altitude_m)
    assert state.temperature > 0.0
    assert state.density > 0.0
    assert not state.approximate


def test_upper_atmosphere_flagged_approximate() -> None:
    state = us_standard_atmosphere(100000.0)
    assert state.approximate


def test_density_decreases_monotonically_with_altitude() -> None:
    altitudes = [0.0, 5000.0, 11000.0, 20000.0, 32000.0]
    densities = [us_standard_atmosphere(a).density for a in altitudes]
    assert all(densities[i] > densities[i + 1] for i in range(len(densities) - 1))
