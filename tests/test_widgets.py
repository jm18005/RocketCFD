"""Reusable GUI widgets: CollapsibleSection folding and UnitValueBox unit conversion."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from rocketcfd.gui.widgets import CollapsibleSection, UnitValueBox


def test_collapsible_section_starts_collapsed_by_default() -> None:
    section = CollapsibleSection("Advanced")
    section.addWidget(QLabel("inside"))
    assert section._body.isHidden() is True


def test_collapsible_section_can_start_expanded() -> None:
    section = CollapsibleSection("Advanced", expanded=True)
    assert section._body.isHidden() is False


def test_collapsible_section_set_expanded_shows_and_hides_body() -> None:
    section = CollapsibleSection("Advanced")
    section.set_expanded(True)
    assert section._body.isHidden() is False
    assert section._toggle.isChecked() is True
    section.set_expanded(False)
    assert section._body.isHidden() is True
    assert section._toggle.isChecked() is False


def test_unit_value_box_converts_between_units() -> None:
    units = {"m": "m", "ft": "ft"}
    box = UnitValueBox("m", units, "m", 0.0, 1000.0, 10.0)
    assert box.value() == pytest.approx(10.0)
    box.unit_combo.setCurrentText("ft")
    assert box.spin.value() == pytest.approx(32.808, abs=1e-2)
    assert box.value() == pytest.approx(10.0)


def test_unit_value_box_set_value_updates_display() -> None:
    units = {"m": "m", "ft": "ft"}
    box = UnitValueBox("m", units, "ft", 0.0, 1000.0, 0.0)
    box.setValue(5.0)
    assert box.value() == pytest.approx(5.0)
