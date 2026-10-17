"""Deployment tab: automated WSL2/OpenFOAM install, TACC batch submission, and UT Box
upload of results."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rocketcfd.box_integration import BoxUploadError, upload_results_folder
from rocketcfd.deployment import (
    install_openfoam_in_wsl,
    install_openfoam_native,
    install_wsl_distro,
    is_windows_host,
)
from rocketcfd.gui.main_window import MainWindow
from rocketcfd.gui.widgets import NoScrollDoubleSpinBox, labeled_row
from rocketcfd.tacc import TaccSettings, TaccSubmissionError, submit_job

INSTALL_WSL_TOOLTIP = "Install WSL2 plus Ubuntu (requires a reboot on first-ever WSL install before it is usable)."
INSTALL_OPENFOAM_TOOLTIP = "Install OpenFOAM via the openfoam.org apt repository, in WSL or directly on this Linux host."
TACC_HOST_TOOLTIP = "TACC login node hostname, e.g. ls6.tacc.utexas.edu."
TACC_USERNAME_TOOLTIP = "Your TACC username."
TACC_ALLOCATION_TOOLTIP = "TACC allocation/project name to charge this job to."
TACC_REMOTE_ROOT_TOOLTIP = "Remote directory on TACC to upload and run cases in."
TACC_QUEUE_TOOLTIP = "SLURM queue/partition name."
TACC_NODES_TOOLTIP = "Number of compute nodes to request."
TACC_TASKS_TOOLTIP = "MPI tasks per node."
TACC_WALLTIME_TOOLTIP = "Requested walltime, HH:MM:SS."
TACC_SSH_KEY_TOOLTIP = "Path to an SSH private key for TACC, or blank to use the default key."
TACC_SUBMIT_TOOLTIP = "Uploads the selected case (from the Automation tab's results table) and submits it as a SLURM job."
BOX_TOKEN_TOOLTIP = "Box OAuth access token (see https://developer.box.com)."
BOX_FOLDER_TOOLTIP = "Box folder id to upload into; a subfolder is created for this case root."
BOX_UPLOAD_TOOLTIP = "Uploads every file in the current case directory (from the Automation tab) to the Box folder above."


class InstallWorker(QThread):
    log = Signal(str)
    failed = Signal(str)
    succeeded = Signal()

    def __init__(self, action: str, automation_panel: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._action = action
        self._automation_panel = automation_panel

    def run(self) -> None:  # noqa: 21 (QThread override, invoked by Qt via .start())
        try:
            if self._action == "wsl":
                install_wsl_distro(self.log.emit)
            elif self._action == "openfoam_wsl":
                install_openfoam_in_wsl(self._automation_panel.wsl_settings_snapshot(), self.log.emit)
            else:
                install_openfoam_native(self.log.emit)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit()


class TaccWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, case_dir: Path, application: str, settings: TaccSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._case_dir = case_dir
        self._application = application
        self._settings = settings

    def run(self) -> None:  # noqa: 21 (QThread override, invoked by Qt via .start())
        try:
            job_id = submit_job(self._case_dir, self._application, self._settings)
        except TaccSubmissionError as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(job_id)


class DeploymentPanel(QWidget):
    def __init__(self, automation_panel: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._automation_panel = automation_panel
        self._install_worker: InstallWorker | None = None
        self._tacc_worker: TaccWorker | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_install_box())
        layout.addWidget(self._build_tacc_box())
        layout.addWidget(self._build_box_upload_box())

        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, stretch=1)

    def _build_install_box(self) -> QGroupBox:
        box = QGroupBox("Install OpenFOAM", self)
        install_layout = QHBoxLayout(box)
        if is_windows_host():
            wsl_button = QPushButton("Install WSL2 (Ubuntu)", box)
            wsl_button.setToolTip(INSTALL_WSL_TOOLTIP)
            wsl_button.clicked.connect(lambda: self._on_install("wsl"))
            install_layout.addWidget(wsl_button)
            openfoam_button = QPushButton("Install OpenFOAM in WSL", box)
            openfoam_button.setToolTip(INSTALL_OPENFOAM_TOOLTIP)
            openfoam_button.clicked.connect(lambda: self._on_install("openfoam_wsl"))
            install_layout.addWidget(openfoam_button)
        else:
            openfoam_button = QPushButton("Install OpenFOAM (native)", box)
            openfoam_button.setToolTip(INSTALL_OPENFOAM_TOOLTIP)
            openfoam_button.clicked.connect(lambda: self._on_install("openfoam_native"))
            install_layout.addWidget(openfoam_button)
        install_layout.addStretch(1)
        return box

    def _on_install(self, action: str) -> None:
        if self._install_worker is not None and self._install_worker.isRunning():
            return
        self._install_worker = InstallWorker(action, self._automation_panel, self)
        self._install_worker.log.connect(self.log_view.appendPlainText)
        self._install_worker.failed.connect(lambda message: self.log_view.appendPlainText(f"Install failed: {message}"))
        self._install_worker.succeeded.connect(lambda: self.log_view.appendPlainText("Install finished."))
        self._install_worker.start()

    def _build_tacc_box(self) -> QGroupBox:
        box = QGroupBox("TACC submission", self)
        tacc_layout = QVBoxLayout(box)
        self.tacc_host_edit = QLineEdit(box)
        self.tacc_host_edit.setToolTip(TACC_HOST_TOOLTIP)
        self.tacc_username_edit = QLineEdit(box)
        self.tacc_username_edit.setToolTip(TACC_USERNAME_TOOLTIP)
        self.tacc_allocation_edit = QLineEdit(box)
        self.tacc_allocation_edit.setToolTip(TACC_ALLOCATION_TOOLTIP)
        self.tacc_remote_root_edit = QLineEdit(box)
        self.tacc_remote_root_edit.setToolTip(TACC_REMOTE_ROOT_TOOLTIP)
        self.tacc_queue_edit = QLineEdit("normal", box)
        self.tacc_queue_edit.setToolTip(TACC_QUEUE_TOOLTIP)
        self.tacc_nodes_spin = NoScrollDoubleSpinBox(box)
        self.tacc_nodes_spin.setDecimals(0)  # noqa: 34 (node count is an integer)
        self.tacc_nodes_spin.setRange(1, 64)
        self.tacc_nodes_spin.setValue(1)
        self.tacc_nodes_spin.setToolTip(TACC_NODES_TOOLTIP)
        self.tacc_tasks_spin = NoScrollDoubleSpinBox(box)
        self.tacc_tasks_spin.setDecimals(0)  # noqa: 34 (tasks-per-node count is an integer)
        self.tacc_tasks_spin.setRange(1, 128)
        self.tacc_tasks_spin.setValue(56)
        self.tacc_tasks_spin.setToolTip(TACC_TASKS_TOOLTIP)
        self.tacc_walltime_edit = QLineEdit("02:00:00", box)
        self.tacc_walltime_edit.setToolTip(TACC_WALLTIME_TOOLTIP)
        self.tacc_ssh_key_edit = QLineEdit(box)
        self.tacc_ssh_key_edit.setToolTip(TACC_SSH_KEY_TOOLTIP)

        tacc_layout.addLayout(labeled_row("Host", self.tacc_host_edit))
        tacc_layout.addLayout(labeled_row("Username", self.tacc_username_edit))
        tacc_layout.addLayout(labeled_row("Allocation", self.tacc_allocation_edit))
        tacc_layout.addLayout(labeled_row("Remote case root", self.tacc_remote_root_edit))
        tacc_layout.addLayout(labeled_row("Queue", self.tacc_queue_edit))
        tacc_layout.addLayout(labeled_row("Nodes", self.tacc_nodes_spin))
        tacc_layout.addLayout(labeled_row("Tasks per node", self.tacc_tasks_spin))
        tacc_layout.addLayout(labeled_row("Walltime", self.tacc_walltime_edit))
        tacc_layout.addLayout(labeled_row("SSH key (optional)", self.tacc_ssh_key_edit))

        submit_button = QPushButton("Submit selected case to TACC", box)
        submit_button.setToolTip(TACC_SUBMIT_TOOLTIP)
        submit_button.clicked.connect(self._on_submit_tacc)
        tacc_layout.addWidget(submit_button)
        return box

    def _on_submit_tacc(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        case = self._automation_panel.selected_case()
        if case is None:
            self.log_view.appendPlainText("No case selected in the Automation tab's results table.")
            return
        settings = TaccSettings(
            host=self.tacc_host_edit.text().strip(),
            username=self.tacc_username_edit.text().strip(),
            allocation=self.tacc_allocation_edit.text().strip(),
            remote_case_root=self.tacc_remote_root_edit.text().strip(),
            queue=self.tacc_queue_edit.text().strip(),
            nodes=int(self.tacc_nodes_spin.value()),
            tasks_per_node=int(self.tacc_tasks_spin.value()),
            walltime=self.tacc_walltime_edit.text().strip(),
            ssh_key_path=self.tacc_ssh_key_edit.text().strip(),
        )
        self.log_view.appendPlainText(f"Submitting {case.case_dir} to TACC...")
        self._tacc_worker = TaccWorker(case.case_dir, case.application, settings, self)
        self._tacc_worker.succeeded.connect(lambda job_id: self.log_view.appendPlainText(f"Submitted; SLURM job id {job_id}."))
        self._tacc_worker.failed.connect(lambda message: self.log_view.appendPlainText(f"TACC submission failed: {message}"))
        self._tacc_worker.start()

    def _build_box_upload_box(self) -> QGroupBox:
        box = QGroupBox("UT Box upload", self)
        box_layout = QVBoxLayout(box)
        self.box_token_edit = QLineEdit(box)
        self.box_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.box_token_edit.setToolTip(BOX_TOKEN_TOOLTIP)
        self.box_folder_edit = QLineEdit(box)
        self.box_folder_edit.setToolTip(BOX_FOLDER_TOOLTIP)
        box_layout.addLayout(labeled_row("Access token", self.box_token_edit))
        box_layout.addLayout(labeled_row("Parent folder id", self.box_folder_edit))
        upload_button = QPushButton("Upload case directory to Box", box)
        upload_button.setToolTip(BOX_UPLOAD_TOOLTIP)
        upload_button.clicked.connect(self._on_upload_box)
        box_layout.addWidget(upload_button)
        return box

    def _on_upload_box(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        case_root = self._automation_panel.execution_backend().case_root
        if not case_root.exists():
            self.log_view.appendPlainText(f"Case root {case_root} does not exist.")
            return
        try:
            file_ids = upload_results_folder(
                self.box_token_edit.text().strip(), self.box_folder_edit.text().strip(), case_root, case_root.name,
            )
        except BoxUploadError as exc:
            self.log_view.appendPlainText(f"Box upload failed: {exc}")
            return
        self.log_view.appendPlainText(f"Uploaded {len(file_ids)} file(s) to Box.")
