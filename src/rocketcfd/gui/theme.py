"""Centralized color palette and QSS stylesheet: the only module allowed hex color
literals, so the whole app stays visually consistent from one place."""
from __future__ import annotations

BACKGROUND = "#1e1f26"
SURFACE = "#262832"
SURFACE_RAISED = "#2f313d"
BORDER = "#3a3d4a"
TEXT_PRIMARY = "#e8e9ee"
TEXT_SECONDARY = "#a3a6b5"
ACCENT = "#ff6a3d"
ACCENT_HOVER = "#ff8256"
ACCENT_PRESSED = "#e2582e"
SUCCESS = "#4caf78"
DANGER = "#e2564e"
DISABLED_TEXT = "#6b6e7c"

FONT_FAMILY = "Segoe UI, Arial, sans-serif"
BASE_FONT_SIZE_PT = 10


def build_stylesheet() -> str:
    return f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {BASE_FONT_SIZE_PT}pt;
}}

QMainWindow, QDialog {{
    background-color: {BACKGROUND};
}}

QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {ACCENT};
}}

QLabel#introLabel {{
    color: {TEXT_SECONDARY};
    padding: 2px 2px 6px 2px;
}}

QLabel#hintLabel {{
    color: {TEXT_SECONDARY};
    font-weight: 400;
    font-style: italic;
}}

QLabel#bboxLabel {{
    color: {ACCENT};
    font-weight: 700;
    padding: 4px 2px;
}}

QToolButton {{
    background-color: transparent;
    border: none;
    color: {ACCENT};
    font-weight: 600;
    padding: 3px 0;
    text-align: left;
}}

QToolButton:hover {{
    color: {ACCENT_HOVER};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {SURFACE};
}}

QTabBar::tab {{
    background-color: {SURFACE};
    color: {TEXT_SECONDARY};
    padding: 7px 16px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    background-color: {SURFACE_RAISED};
    color: {TEXT_PRIMARY};
    border-bottom: 2px solid {ACCENT};
}}

QPushButton {{
    background-color: {SURFACE_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 14px;
}}

QPushButton:hover {{
    border-color: {ACCENT};
}}

QPushButton:pressed {{
    background-color: {ACCENT_PRESSED};
    color: {TEXT_PRIMARY};
}}

QPushButton:disabled {{
    color: {DISABLED_TEXT};
}}

QPushButton#primaryAction {{
    background-color: {ACCENT};
    color: {BACKGROUND};
    font-weight: 700;
    border: none;
}}

QPushButton#primaryAction:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primaryAction:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton#primaryAction:disabled {{
    background-color: {SURFACE_RAISED};
    color: {DISABLED_TEXT};
}}

QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background-color: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 3px 6px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
}}

QTableWidget {{
    background-color: {BACKGROUND};
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: {BACKGROUND};
}}

QHeaderView::section {{
    background-color: {SURFACE_RAISED};
    color: {TEXT_PRIMARY};
    padding: 4px;
    border: 1px solid {BORDER};
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    background-color: {BACKGROUND};
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: {SURFACE};
    border: none;
}}

QScrollBar::handle {{
    background: {BORDER};
    border-radius: 4px;
}}

QScrollBar::handle:hover {{
    background: {ACCENT};
}}

QSplitter::handle {{
    background-color: {BORDER};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
}}

QToolTip {{
    background-color: {SURFACE_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {ACCENT};
    padding: 4px;
}}
"""
