"""Reusable GUI widgets: scroll-safe inputs and a unit-converting value box."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (  # noqa: 31 (this module defines the no-scroll wrapper)
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QWheelEvent

from rocketcfd.gui.tooltips import COLLAPSIBLE_SECTION_TOGGLE_TOOLTIP
from rocketcfd.gui.units import from_base, to_base


def labeled_row(label: str | QWidget, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addWidget(QLabel(label) if isinstance(label, str) else label)
    row.addWidget(widget)
    return row


class CollapsibleSection(QWidget):
    """A named, foldable group of settings. Starts collapsed by default so a beginner's
    first screen only shows the handful of controls they actually need; anything inside
    stays fully functional (and readable by tests) whether or not it is expanded."""

    def __init__(self, title: str, parent: QWidget | None = None, expanded: bool = False) -> None:
        super().__init__(parent)
        self._toggle = QToolButton(self)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toggle.setCheckable(True)
        self._toggle.setText(title)
        self._toggle.setToolTip(COLLAPSIBLE_SECTION_TOGGLE_TOOLTIP)
        self._toggle.clicked.connect(self._on_toggled)

        self._body = QWidget(self)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(12, 4, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toggle)
        layout.addWidget(self._body)

        self.set_expanded(expanded)

    def _on_toggled(self, checked: bool) -> None:
        self.set_expanded(checked)

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.setChecked(expanded)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._body.setVisible(expanded)

    def addWidget(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def addLayout(self, item_layout: QLayout) -> None:
        self._body_layout.addLayout(item_layout)


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: 21 (Qt event override)
        event.ignore()


class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: 21 (Qt event override)
        event.ignore()


class UnitValueBox(QWidget):
    """A spinbox + unit dropdown pair. Value is stored/reported in a fixed base unit
    (SI) regardless of which display unit is currently selected, so callers never need
    to know which unit the user picked."""

    valueChanged = Signal(float)

    def __init__(
        self,
        base_unit: str,
        units: dict[str, str],
        default_unit: str,
        minimum: float,
        maximum: float,
        value: float,
        parent: QWidget | None = None,
        decimals: int = 4,
        tooltip: str = "",
    ) -> None:
        super().__init__(parent)
        self._base_unit = base_unit
        self._units = units
        self._minimum = minimum
        self._maximum = maximum
        self._base_value = value

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.spin = NoScrollDoubleSpinBox(self)
        self.spin.setDecimals(decimals)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        if tooltip:
            self.spin.setToolTip(tooltip)
        self.unit_combo = NoScrollComboBox(self)
        self.unit_combo.addItems(list(units.keys()))
        self.unit_combo.setCurrentText(default_unit)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.unit_combo)

        self._apply_range_for_current_unit()
        self.spin.setValue(from_base(value, self._current_unit(), base_unit))
        self.spin.valueChanged.connect(self._on_spin_changed)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)

    def _current_unit(self) -> str:
        return self._units[self.unit_combo.currentText()]

    def _apply_range_for_current_unit(self) -> None:
        unit = self._current_unit()
        lo = from_base(self._minimum, unit, self._base_unit)
        hi = from_base(self._maximum, unit, self._base_unit)
        self.spin.setRange(min(lo, hi), max(lo, hi))

    def _on_spin_changed(self, displayed_value: float) -> None:  # noqa: 21 (Qt slot signature)
        self._base_value = to_base(displayed_value, self._current_unit(), self._base_unit)
        self.valueChanged.emit(self._base_value)

    def _on_unit_changed(self, _new_label: str) -> None:  # noqa: 21 (Qt slot signature)
        self._apply_range_for_current_unit()
        self.spin.blockSignals(True)
        self.spin.setValue(from_base(self._base_value, self._current_unit(), self._base_unit))
        self.spin.blockSignals(False)

    def value(self) -> float:
        return self._base_value

    def setValue(self, base_value: float) -> None:
        self._base_value = base_value
        self.spin.blockSignals(True)
        self.spin.setValue(from_base(base_value, self._current_unit(), self._base_unit))
        self.spin.blockSignals(False)
