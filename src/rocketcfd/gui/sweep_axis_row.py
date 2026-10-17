"""Shared flow-condition sweep-axis row widget."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from rocketcfd.gui.sweep_variables import SWEEP_VARIABLES
from rocketcfd.gui.units import from_base, to_base
from rocketcfd.gui.widgets import NoScrollComboBox
from rocketcfd.sweep import SWEEP_SYNTAX_HELP, SweepAxis, parse_values


class SweepAxisRow(QWidget):
    """One flow-condition variable's value spec: blank means 'leave at zero/unset', a
    single value fixes it, and a list/range (comma list, MATLAB-style start:step:stop,
    or start;stop;count) makes it a swept axis for this run."""

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        var = SWEEP_VARIABLES[key]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.unit_combo = NoScrollComboBox(self)
        if var.units:
            self.unit_combo.addItems(list(var.units.keys()))
            base_label = next(label for label, unit in var.units.items() if unit == var.base_unit)
            self.unit_combo.setCurrentText(base_label)
        else:
            self.unit_combo.addItem("-")
            self.unit_combo.setEnabled(False)

        self.values_edit = QLineEdit(self)
        self.values_edit.setPlaceholderText(f"blank = unused, e.g. {var.example}")
        self.values_edit.setToolTip(SWEEP_SYNTAX_HELP)

        layout.addWidget(self.unit_combo)
        layout.addWidget(self.values_edit, 1)

        if var.default is not None:
            self.set_single_value(var.default)

    def axis(self) -> SweepAxis | None:
        text = self.values_edit.text().strip()
        if not text:
            return None
        values = parse_values(text)
        var = SWEEP_VARIABLES[self.key]
        if var.units:
            unit = var.units[self.unit_combo.currentText()]
            values = np.array([to_base(v, unit, var.base_unit) for v in values])
        return SweepAxis(self.key, values)

    def set_single_value(self, base_value: float) -> None:
        var = SWEEP_VARIABLES[self.key]
        display = base_value
        if var.units:
            unit = var.units[self.unit_combo.currentText()]
            display = from_base(base_value, unit, var.base_unit)
        self.values_edit.setText(f"{display:.6g}")
