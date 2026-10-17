"""Sizes the first snappyHexMesh boundary-layer cell to hit a target y+, using a
flat-plate turbulent skin-friction correlation as a conservative estimate rather than a
full boundary-layer solve."""
from __future__ import annotations

SKIN_FRICTION_COEFFICIENT = 0.058
SKIN_FRICTION_REYNOLDS_EXPONENT = -0.2


def first_layer_thickness(y_plus_target: float, velocity: float, density: float, dynamic_viscosity: float, reference_length: float) -> float:
    """Returns the absolute first-cell height (m) that puts the wall-adjacent cell center
    at y_plus_target, for a flat-plate turbulent boundary layer at the given freestream
    velocity/density/viscosity over reference_length."""
    if velocity <= 0.0:
        raise ValueError("velocity must be positive")
    if reference_length <= 0.0:
        raise ValueError("reference_length must be positive")
    kinematic_viscosity = dynamic_viscosity / density
    reynolds = velocity * reference_length / kinematic_viscosity
    skin_friction = SKIN_FRICTION_COEFFICIENT * reynolds**SKIN_FRICTION_REYNOLDS_EXPONENT
    wall_shear = 0.5 * skin_friction * density * velocity**2
    friction_velocity = (wall_shear / density) ** 0.5
    return y_plus_target * kinematic_viscosity / friction_velocity
