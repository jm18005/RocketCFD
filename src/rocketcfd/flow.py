"""Freestream flow condition definitions."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from rocketcfd.gas import GAMMA_AIR, speed_of_sound

SEA_LEVEL_DENSITY = 1.225
SEA_LEVEL_TEMPERATURE = 288.15


def wind_unit(wind_direction_deg: float, wind_elevation_deg: float = 0.0) -> np.ndarray:
    """Unit vector the wind blows toward: azimuth measured from +X toward +Y in the
    horizontal (X-Y) plane, elevation measured up from that plane toward +Z."""
    azimuth = np.radians(wind_direction_deg)
    elevation = np.radians(wind_elevation_deg)
    return np.array(
        [np.cos(elevation) * np.cos(azimuth), np.cos(elevation) * np.sin(azimuth), np.sin(elevation)]
    )


@dataclass
class FlowCondition:
    name: str
    velocity: float
    alpha_deg: float
    beta_deg: float
    density: float = SEA_LEVEL_DENSITY
    temperature: float = SEA_LEVEL_TEMPERATURE
    gamma: float = GAMMA_AIR
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    adiabatic_wall: bool = True
    wall_temperature: float = SEA_LEVEL_TEMPERATURE
    wind_speed: float = 0.0
    wind_direction_deg: float = 0.0
    wind_elevation_deg: float = 0.0

    def dynamic_pressure(self) -> float:
        return 0.5 * self.density * self.velocity**2

    def mach(self) -> float:
        return self.velocity / speed_of_sound(self.temperature, self.gamma)

    def direction_unit(self) -> np.ndarray:
        alpha = np.radians(self.alpha_deg)
        beta = np.radians(self.beta_deg)
        return np.array(
            [
                np.cos(alpha) * np.cos(beta),
                np.sin(beta),
                np.sin(alpha) * np.cos(beta),
            ]
        )

    def up_unit(self) -> np.ndarray:
        up = np.asarray(self.up, dtype=np.float64)
        return up / np.linalg.norm(up)

    def effective_condition(self) -> "FlowCondition":
        """The relative-wind condition actually solved for: the vehicle's own motion
        combined vectorially with the ambient wind, so the OpenFOAM boundary condition
        (and the coefficients derived from it) reflect true relative airspeed rather
        than ground speed. Returns self unchanged when there is no wind."""
        if self.wind_speed <= 0.0:
            return self
        vector = self.velocity * self.direction_unit() + self.wind_speed * wind_unit(self.wind_direction_deg, self.wind_elevation_deg)
        velocity, alpha_deg, beta_deg = velocity_alpha_beta(vector)
        return replace(
            self, velocity=velocity, alpha_deg=alpha_deg, beta_deg=beta_deg,
            wind_speed=0.0, wind_direction_deg=0.0, wind_elevation_deg=0.0,
        )


def velocity_alpha_beta(vector: np.ndarray) -> tuple[float, float, float]:
    """Inverse of FlowCondition.direction_unit(): recovers (velocity, alpha_deg, beta_deg)
    from a dimensional velocity vector, e.g. one read back from an OpenFOAM U field."""
    velocity = float(np.linalg.norm(vector))
    if velocity == 0.0:
        return 0.0, 0.0, 0.0
    unit = vector / velocity
    beta_deg = float(np.degrees(np.arcsin(np.clip(unit[1], -1.0, 1.0))))
    alpha_deg = float(np.degrees(np.arctan2(unit[2], unit[0])))
    return velocity, alpha_deg, beta_deg
