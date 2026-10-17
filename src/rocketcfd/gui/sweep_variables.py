"""Unit-aware metadata for sweepable flow-condition variables, used by the main window."""
from __future__ import annotations

from dataclasses import dataclass

from rocketcfd.flow import SEA_LEVEL_DENSITY, SEA_LEVEL_TEMPERATURE
from rocketcfd.gui.units import DENSITY_UNITS, LENGTH_UNITS, TEMPERATURE_UNITS, VELOCITY_UNITS


@dataclass
class SweepVariable:
    label: str
    base_unit: str | None
    units: dict[str, str] | None
    example: str
    default: float | None = None


SWEEP_VARIABLES: dict[str, SweepVariable] = {
    "mach": SweepVariable("Mach", None, None, "1:0.5:10", default=None),
    "velocity": SweepVariable("Velocity", "m/s", VELOCITY_UNITS, "10, 20, 50", default=30.0),
    "altitude": SweepVariable("Altitude", "m", LENGTH_UNITS, "0;20000;50", default=None),
    "density": SweepVariable("Density", "kg/m**3", DENSITY_UNITS, "1.225", default=SEA_LEVEL_DENSITY),
    "temperature": SweepVariable(
        "Static temperature", "kelvin", TEMPERATURE_UNITS, "288.15", default=SEA_LEVEL_TEMPERATURE
    ),
    "alpha_deg": SweepVariable("Alpha (deg)", None, None, "0:1:15", default=0.0),
    "beta_deg": SweepVariable("Beta (deg)", None, None, "0", default=0.0),
}
