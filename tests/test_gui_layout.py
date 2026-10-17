"""Regression guard against clipped/cut-off controls: at both the app's default and
enforced-minimum window sizes, every visible label/button/input in the Automation tab
must get at least its own minimum size hint's worth of space, and the control panel's
scroll area must be wide enough to show its content without needing to scroll sideways."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QWidget,
)

from rocketcfd.gui.app_window import AppWindow
from rocketcfd.gui.main_window import MainWindow
from rocketcfd.gui.widgets import CollapsibleSection

_LEAF_TYPES = (QLabel, QPushButton, QCheckBox, QComboBox, QLineEdit, QAbstractSpinBox)


def _leaf_widgets(root: QWidget) -> Iterator[QWidget]:
    for widget in root.findChildren(QWidget):
        if isinstance(widget, _LEAF_TYPES) and widget.isVisible():
            yield widget


def _clipped_widgets(root: QWidget) -> list[tuple[QWidget, int, int]]:
    offenders = []
    for widget in _leaf_widgets(root):
        min_width = widget.minimumSizeHint().width()
        if min_width > 0 and widget.width() < min_width:
            offenders.append((widget, widget.width(), min_width))
    return offenders


def _describe(offenders: list[tuple[QWidget, int, int]]) -> str:
    def label(widget: QWidget) -> str:
        if isinstance(widget, (QLabel, QPushButton, QCheckBox)):
            return f"{type(widget).__name__}({widget.text()!r})"
        return f"{type(widget).__name__}({widget.objectName()!r})"

    return "; ".join(f"{label(w)} got {actual}px, needs {needed}px" for w, actual, needed in offenders)


@pytest.fixture
def app_window(qapp: QApplication) -> Iterator[AppWindow]:  # noqa: 21 (pytest fixture, injected by name into the test functions below)
    win = AppWindow()
    win.show()
    yield win
    win.close()


def _settle() -> None:
    QApplication.processEvents()
    QApplication.processEvents()


def _expand_all_collapsible_sections(automation: MainWindow) -> None:
    for section in automation.findChildren(CollapsibleSection):
        section.set_expanded(True)
    automation.ref_dims_override_checkbox.setChecked(True)


@pytest.mark.parametrize("width,height", [(1500, 950), (1100, 700)])
def test_automation_tab_has_no_clipped_controls(app_window: AppWindow, width: int, height: int) -> None:
    app_window.resize(width, height)
    _settle()
    automation = app_window.findChild(MainWindow)
    _expand_all_collapsible_sections(automation)
    _settle()

    scroll = automation.findChild(QScrollArea)
    control_offenders = _clipped_widgets(scroll.widget())
    assert not control_offenders, f"Control panel has clipped widgets: {_describe(control_offenders)}"

    for tab_index in range(automation.view_tabs.count()):
        automation.view_tabs.setCurrentIndex(tab_index)
        _settle()
        page_offenders = _clipped_widgets(automation.view_tabs.currentWidget())
        assert not page_offenders, f"View tab {tab_index} has clipped widgets: {_describe(page_offenders)}"


@pytest.mark.parametrize("width,height", [(1500, 950), (1100, 700)])
def test_control_panel_scroll_area_never_needs_sideways_scrolling(app_window: AppWindow, width: int, height: int) -> None:
    app_window.resize(width, height)
    _settle()
    automation = app_window.findChild(MainWindow)
    _expand_all_collapsible_sections(automation)
    _settle()

    scroll = automation.findChild(QScrollArea)
    assert scroll.widget().minimumSizeHint().width() <= scroll.viewport().width()


def test_splitter_cannot_be_dragged_to_collapse_a_pane(app_window: AppWindow) -> None:
    automation = app_window.findChild(MainWindow)
    splitter = automation.findChild(QSplitter)
    assert splitter.childrenCollapsible() is False
