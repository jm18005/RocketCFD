"""Analytic/tabulated reference values for proven, simple validation geometries: flat
plate skin friction, sphere drag, and slender-cone supersonic wave drag."""
from __future__ import annotations

import numpy as np

FLAT_PLATE_TRANSITION_REYNOLDS = 5.0e5

# Standard sphere Cd-vs-Re curve (subcritical plateau, drag crisis near Re~3e5, recovery),
# digitized from Schlichting & Gersten, "Boundary-Layer Theory."
_SPHERE_CD_LOG10_RE = np.array([1.0, 2.0, 3.0, 3.5, 4.0, 4.5, 5.0, 5.3, 5.48, 5.7, 6.0, 6.5, 7.0])
_SPHERE_CD = np.array([3.0, 1.5, 0.5, 0.4, 0.47, 0.5, 0.5, 0.4, 0.1, 0.1, 0.13, 0.18, 0.2])


def flat_plate_cf(reynolds_length: float, transition_reynolds: float = FLAT_PLATE_TRANSITION_REYNOLDS) -> float:
    """Mean skin-friction coefficient over a flat plate of length L, at Reynolds number
    reynolds_length = velocity*L/nu: Blasius laminar solution below transition, Prandtl's
    one-seventh-power-law turbulent correlation above it."""
    if reynolds_length <= 0.0:
        raise ValueError("reynolds_length must be positive")
    if reynolds_length < transition_reynolds:
        return 1.328 / np.sqrt(reynolds_length)
    return 0.074 / reynolds_length**0.2


def sphere_cd_reference(reynolds_diameter: float) -> float:
    """Standard sphere drag coefficient at Reynolds number reynolds_diameter =
    velocity*diameter/nu, log-log interpolated from the digitized reference curve."""
    if reynolds_diameter <= 0.0:
        raise ValueError("reynolds_diameter must be positive")
    log_re = np.log10(reynolds_diameter)
    return float(np.interp(log_re, _SPHERE_CD_LOG10_RE, _SPHERE_CD))


def slender_cone_wave_drag_cd(half_angle_deg: float, mach: float) -> float:
    """Linearized supersonic slender-body wave-drag coefficient for a sharp cone at zero
    angle of attack, Cd = 4*theta^2/sqrt(M^2-1) (theta in radians): a coarse approximation
    valid for small half-angles and M well above 1, not a full Taylor-Maccoll solution."""
    if mach <= 1.0:
        raise ValueError("slender_cone_wave_drag_cd requires supersonic Mach (M > 1)")
    theta = np.radians(half_angle_deg)
    return float(4.0 * theta**2 / np.sqrt(mach**2 - 1.0))
