"""Calorically-perfect-air constants and simple gas relations."""
from __future__ import annotations

import numpy as np

R_AIR = 287.05
GAMMA_AIR = 1.4
SUTHERLAND_MU_REF = 1.716e-5
SUTHERLAND_T_REF = 273.15
SUTHERLAND_S = 110.4


def sutherland_viscosity(temperature: float) -> float:
    t_ratio = temperature / SUTHERLAND_T_REF
    return SUTHERLAND_MU_REF * t_ratio**1.5 * (SUTHERLAND_T_REF + SUTHERLAND_S) / (temperature + SUTHERLAND_S)


def speed_of_sound(temperature: float, gamma: float = GAMMA_AIR) -> float:
    return float(np.sqrt(gamma * R_AIR * temperature))


def static_pressure(density: float, temperature: float) -> float:
    return density * R_AIR * temperature
