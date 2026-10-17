"""pint-backed unit registry and dropdown-label -> unit-string tables for the GUI."""
from __future__ import annotations

import pint

ureg = pint.UnitRegistry()
ureg.define("kilofoot = 1000 * foot = kft")

VELOCITY_UNITS = {
    "m/s": "m/s",
    "km/h": "km/h",
    "ft/s": "ft/s",
    "mph": "mph",
    "knots": "knot",
}

LENGTH_UNITS = {
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "km": "km",
    "in": "in",
    "ft": "ft",
    "kft": "kft",
    "mi": "mi",
    "nmi": "nmi",
}

AREA_UNITS = {
    "mm^2": "mm**2",
    "cm^2": "cm**2",
    "m^2": "m**2",
    "in^2": "in**2",
    "ft^2": "ft**2",
}

DENSITY_UNITS = {
    "kg/m^3": "kg/m**3",
    "slug/ft^3": "slug/ft**3",
    "lb/ft^3": "lb/ft**3",
}

TEMPERATURE_UNITS = {
    "K": "kelvin",
    "C": "degC",
    "F": "degF",
    "R": "degR",
}

def to_base(value: float, unit: str, base_unit: str) -> float:
    return float(ureg.Quantity(value, unit).to(base_unit).magnitude)


def from_base(value: float, unit: str, base_unit: str) -> float:
    return float(ureg.Quantity(value, base_unit).to(unit).magnitude)
