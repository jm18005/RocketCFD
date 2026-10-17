"""Force/moment -> aerodynamic coefficients."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rocketcfd.flow import FlowCondition


@dataclass
class Coefficients:
    cd: float
    cl: float
    cs: float
    cm: np.ndarray


def from_force_moment(
    condition: FlowCondition,
    force: np.ndarray,
    moment: np.ndarray,
    reference_area: float,
    reference_length: float,
) -> Coefficients:
    direction = condition.direction_unit()
    up = condition.up_unit()
    side_dir = np.cross(direction, up)
    side_dir = side_dir / np.linalg.norm(side_dir)
    lift_dir = np.cross(side_dir, direction)

    q = condition.dynamic_pressure()
    denom = q * reference_area if reference_area > 0.0 else 1.0
    return Coefficients(
        cd=force @ direction / denom,
        cl=force @ lift_dir / denom,
        cs=force @ side_dir / denom,
        cm=moment / (denom * reference_length),
    )
