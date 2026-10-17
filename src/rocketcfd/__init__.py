"""RocketCFD: automated OpenFOAM CFD tool for LRA rocket aerodynamics."""
import sys

from PySide6.QtWidgets import QApplication

from rocketcfd.gui.app_window import AppWindow
from rocketcfd.gui.theme import build_stylesheet


def main() -> None:  # noqa: 21 (entry point declared in pyproject.toml)
    app = QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())
    window = AppWindow()
    window.showMaximized()
    sys.exit(app.exec())
