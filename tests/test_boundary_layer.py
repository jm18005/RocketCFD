"""Target-y+ first-layer-thickness sizing."""
from __future__ import annotations

import pytest

from rocketcfd.openfoam.boundary_layer import first_layer_thickness


def test_first_layer_thickness_is_positive() -> None:
    thickness = first_layer_thickness(
        y_plus_target=1.0, velocity=50.0, density=1.225, dynamic_viscosity=1.8e-5, reference_length=1.0,
    )
    assert thickness > 0.0


def test_higher_target_y_plus_gives_thicker_layer() -> None:
    thin = first_layer_thickness(1.0, 50.0, 1.225, 1.8e-5, 1.0)
    thick = first_layer_thickness(30.0, 50.0, 1.225, 1.8e-5, 1.0)
    assert thick > thin
    assert thick == pytest.approx(thin * 30.0, rel=1e-9)


def test_higher_velocity_gives_thinner_layer_at_fixed_y_plus() -> None:
    slow = first_layer_thickness(1.0, 20.0, 1.225, 1.8e-5, 1.0)
    fast = first_layer_thickness(1.0, 200.0, 1.225, 1.8e-5, 1.0)
    assert fast < slow


def test_non_positive_velocity_raises() -> None:
    with pytest.raises(ValueError):
        first_layer_thickness(1.0, 0.0, 1.225, 1.8e-5, 1.0)


def test_non_positive_reference_length_raises() -> None:
    with pytest.raises(ValueError):
        first_layer_thickness(1.0, 50.0, 1.225, 1.8e-5, 0.0)
