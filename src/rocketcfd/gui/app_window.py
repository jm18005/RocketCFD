"""Top-level window: Automation, Validation, and Deployment tabs."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from rocketcfd.gui.deployment_panel import DeploymentPanel
from rocketcfd.gui.main_window import MainWindow
from rocketcfd.gui.validation_panel import ValidationPanel


class AppWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RocketCFD")
        self.setMinimumSize(1100, 700)
        self.resize(1500, 950)

        tabs = QTabWidget(self)
        automation_panel = MainWindow(tabs)
        tabs.addTab(automation_panel, "Automation")
        tabs.addTab(ValidationPanel(automation_panel, tabs), "Validation")
        tabs.addTab(DeploymentPanel(automation_panel, tabs), "Deployment")
        self.setCentralWidget(tabs)
