"""Builds flow-condition sweeps (1D lines or N-D grids) for batch runs."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace

import numpy as np

from rocketcfd.atmosphere import us_standard_atmosphere
from rocketcfd.flow import FlowCondition
from rocketcfd.gas import speed_of_sound

_APPLY_PRIORITY = {
    "altitude": 0,
    "density": 0,
    "temperature": 0,
    "wall_temperature": 0,
    "gamma": 0,
    "alpha_deg": 0,
    "beta_deg": 0,
    "velocity": 0,
    "mach": 1,
}


SWEEP_SYNTAX_HELP = (
    "Single value: 5\n"
    "List: 1, 1.5, 2\n"
    "Step range (MATLAB-style start:step:stop): 1:10:1000 -> 1 to 1000 in steps of 10\n"
    "Count range (start;stop;count): 1;10;1000 -> 1000 points from 1 to 10"
)


@dataclass
class SweepAxis:
    variable: str
    values: np.ndarray


def parse_values(text: str) -> np.ndarray:
    """Parses a sweep-axis value spec; see SWEEP_SYNTAX_HELP for the accepted forms."""
    text = text.strip()
    if ":" in text:
        start_s, step_s, stop_s = text.split(":")
        start, step, stop = float(start_s), float(step_s), float(stop_s)
        if step == 0:
            raise ValueError("step cannot be zero")
        count = int(np.floor((stop - start) / step + 1e-9)) + 1
        if count < 1:
            raise ValueError("range produces no points")
        return np.linspace(start, start + step * (count - 1), count)
    if ";" in text:
        start_s, stop_s, count_s = text.split(";")
        start, stop, count = float(start_s), float(stop_s), int(round(float(count_s)))
        if count < 1:
            raise ValueError("count must be positive")
        return np.linspace(start, stop, count)
    if "," in text:
        return np.array([float(tok.strip()) for tok in text.split(",") if tok.strip()], dtype=np.float64)
    return np.array([float(text)])


def _apply(condition: FlowCondition, variable: str, value: float) -> FlowCondition:
    if variable == "altitude":
        state = us_standard_atmosphere(value)
        return replace(condition, density=state.density, temperature=state.temperature)
    if variable == "mach":
        return replace(condition, velocity=value * speed_of_sound(condition.temperature, condition.gamma))
    return replace(condition, **{variable: value})


def build_conditions(base: FlowCondition, axes: list[SweepAxis]) -> list[FlowCondition]:
    """Cross-product over 1-or-more axes. Variables are applied in priority order (altitude/
    density/temperature/etc. before mach) so a mach axis always converts using whatever
    temperature/gamma resulted from the other axes, regardless of the order axes were given in."""
    order = sorted(range(len(axes)), key=lambda i: _APPLY_PRIORITY[axes[i].variable])
    conditions = []
    for combo in itertools.product(*(axis.values for axis in axes)):
        condition = base
        for i in order:
            condition = _apply(condition, axes[i].variable, combo[i])
        label = ", ".join(f"{axes[i].variable}={combo[i]:.4g}" for i in range(len(axes)))
        conditions.append(replace(condition, name=label))
    return conditions
