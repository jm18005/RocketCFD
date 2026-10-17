"""Sweep-axis value parsing and N-D flow-condition sweep construction."""
from __future__ import annotations

import numpy as np
import pytest

from rocketcfd.flow import FlowCondition
from rocketcfd.sweep import SweepAxis, build_conditions, parse_values


def test_parse_single_value() -> None:
    assert parse_values("5") == pytest.approx([5.0])


def test_parse_comma_list() -> None:
    assert list(parse_values("1, 1.5, 2")) == pytest.approx([1.0, 1.5, 2.0])


def test_parse_step_range() -> None:
    values = parse_values("1:10:1000")
    assert values[0] == pytest.approx(1.0)
    assert values[-1] == pytest.approx(991.0)
    assert len(values) == 100


def test_parse_count_range() -> None:
    values = parse_values("1;10;1000")
    assert len(values) == 1000
    assert values[0] == pytest.approx(1.0)
    assert values[-1] == pytest.approx(10.0)


def test_parse_zero_step_raises() -> None:
    with pytest.raises(ValueError):
        parse_values("1:0:10")


def test_build_conditions_cross_product() -> None:
    base = FlowCondition(name="base", velocity=0.0, alpha_deg=0.0, beta_deg=0.0)
    axes = [SweepAxis("alpha_deg", np.array([0.0, 5.0])), SweepAxis("velocity", np.array([100.0, 200.0]))]
    conditions = build_conditions(base, axes)
    assert len(conditions) == 4
    assert {c.alpha_deg for c in conditions} == {0.0, 5.0}
    assert {c.velocity for c in conditions} == {100.0, 200.0}


def test_mach_axis_applied_after_altitude() -> None:
    base = FlowCondition(name="base", velocity=0.0, alpha_deg=0.0, beta_deg=0.0)
    axes = [SweepAxis("mach", np.array([1.0])), SweepAxis("altitude", np.array([10000.0]))]
    conditions = build_conditions(base, axes)
    assert len(conditions) == 1
    assert abs(conditions[0].mach() - 1.0) < 1e-6
