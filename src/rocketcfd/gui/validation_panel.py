"""Validation tab: runs the built-in sphere/flat-plate/cone suite through the same
OpenFOAM pipeline as the Automation tab and reports pass/fail against reference data."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rocketcfd.gui import theme
from rocketcfd.gui.main_window import MainWindow
from rocketcfd.gui.tooltips import VALIDATION_RUN_TOOLTIP
from rocketcfd.validation.runner import ValidationResult, default_validation_suite, run_validation_suite

RESULT_HEADERS = ["Case", "Computed", "Reference", "Delta %", "Pass/Fail"]


class ValidationWorker(QThread):
    log = Signal(str)
    succeeded = Signal(list)
    failed = Signal(str)

    def __init__(self, automation_panel: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._automation_panel = automation_panel

    def run(self) -> None:  # noqa: 21 (QThread override, invoked by Qt via .start())
        try:
            results = run_validation_suite(
                default_validation_suite(),
                self._automation_panel.execution_backend(),
                self._automation_panel.mesh_settings(),
                self._automation_panel.solver_settings(),
                self.log.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(results)


class ValidationPanel(QWidget):
    def __init__(self, automation_panel: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._automation_panel = automation_panel
        self._worker: ValidationWorker | None = None

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.run_button = QPushButton("Run validation suite", self)
        self.run_button.setObjectName("primaryAction")
        self.run_button.setToolTip(VALIDATION_RUN_TOOLTIP)
        self.run_button.clicked.connect(self._on_run)
        header.addWidget(self.run_button)
        header.addStretch(1)
        layout.addLayout(header)

        self.status_label = QLabel("Uses the execution/mesh/solver settings from the Automation tab.", self)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, len(RESULT_HEADERS), self)
        self.table.setHorizontalHeaderLabels(RESULT_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

    def _on_run(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        if self._worker is not None and self._worker.isRunning():
            return
        self.run_button.setEnabled(False)
        self.status_label.setText("Running validation suite... this can take a while on the first (mesh) case.")
        self._worker = ValidationWorker(self._automation_panel, self)
        self._worker.log.connect(self.status_label.setText)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_succeeded(self, results: list[ValidationResult]) -> None:
        self.run_button.setEnabled(True)
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(result.case_name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{result.computed_value:.4g}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{result.reference_value:.4g}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{result.delta_pct:+.1f}"))
            verdict_item = QTableWidgetItem("PASS" if result.passed else "FAIL")
            verdict_item.setForeground(QColor(theme.SUCCESS if result.passed else theme.DANGER))
            self.table.setItem(row, 4, verdict_item)
        passed = sum(1 for r in results if r.passed)
        self.status_label.setText(f"{passed}/{len(results)} validation case(s) passed.")

    def _on_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.status_label.setText(f"Validation run failed: {message}")
