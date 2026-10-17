"""US Standard Atmosphere 1976, extended above 86 km with a crude exponential tail."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rocketcfd.gas import R_AIR

G0 = 9.80665
TOP_LAYER_ALTITUDE = 84852.0
TOP_LAYER_TEMPERATURE = 186.946
TOP_LAYER_PRESSURE = 3.95642e-1
UPPER_ATMOSPHERE_SCALE_HEIGHT = 50000.0

LAYER_BASE_ALTITUDE = np.array([0.0, 11000.0, 20000.0, 32000.0, 47000.0, 51000.0, 71000.0, TOP_LAYER_ALTITUDE])
LAYER_BASE_TEMPERATURE = np.array([288.15, 216.65, 216.65, 228.65, 270.65, 270.65, 214.65, TOP_LAYER_TEMPERATURE])
LAYER_LAPSE_RATE = np.array([-0.0065, 0.0, 0.001, 0.0028, 0.0, -0.0028, -0.002, 0.0])
LAYER_BASE_PRESSURE = np.array(
    [101325.0, 22632.06, 5474.889, 868.0187, 110.9063, 66.93887, 3.956420, TOP_LAYER_PRESSURE]
)


@dataclass
class AtmosphereState:
    altitude: float
    temperature: float
    pressure: float
    density: float
    approximate: bool


def us_standard_atmosphere(altitude: float) -> AtmosphereState:
    if altitude > TOP_LAYER_ALTITUDE:
        return _upper_atmosphere(altitude)

    layer = int(np.searchsorted(LAYER_BASE_ALTITUDE, altitude, side="right") - 1)
    layer = max(0, min(layer, len(LAYER_BASE_ALTITUDE) - 1))
    h0 = LAYER_BASE_ALTITUDE[layer]
    t0 = LAYER_BASE_TEMPERATURE[layer]
    p0 = LAYER_BASE_PRESSURE[layer]
    lapse = LAYER_LAPSE_RATE[layer]
    dh = altitude - h0

    if abs(lapse) < 1e-12:
        temperature = t0
        pressure = p0 * np.exp(-G0 * dh / (R_AIR * t0))
    else:
        temperature = t0 + lapse * dh
        pressure = p0 * (temperature / t0) ** (-G0 / (lapse * R_AIR))

    density = pressure / (R_AIR * temperature)
    return AtmosphereState(altitude, float(temperature), float(pressure), float(density), False)


def _upper_atmosphere(altitude: float) -> AtmosphereState:
    dh = altitude - TOP_LAYER_ALTITUDE
    temperature = TOP_LAYER_TEMPERATURE
    pressure = TOP_LAYER_PRESSURE * np.exp(-dh / UPPER_ATMOSPHERE_SCALE_HEIGHT)
    density = pressure / (R_AIR * temperature)
    return AtmosphereState(altitude, float(temperature), float(pressure), float(density), True)
