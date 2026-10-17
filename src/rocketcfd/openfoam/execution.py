"""Execution backends abstracting where OpenFOAM commands actually run: inside WSL2 (from
Windows) or directly on a Linux host. case_result.run_openfoam_sweep is written against
this interface so its orchestration logic (mesh once, solve per condition, cache, gate on
mesh quality) is not duplicated per backend."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from rocketcfd.openfoam import runner
from rocketcfd.openfoam.settings import NativeLinuxSettings, WslSettings


class ExecutionBackend(Protocol):
    case_root: Path

    def ensure_ready(self, on_log: Callable[[str], None]) -> None: ...

    def available_processors(self) -> int: ...

    def run(self, commands: list[str], case_dir: Path, on_log: Callable[[str], None]) -> None: ...


@dataclass
class WslExecutionBackend:
    settings: WslSettings

    @property
    def case_root(self) -> Path:
        return self.settings.case_root

    def ensure_ready(self, on_log: Callable[[str], None]) -> None:
        if self.settings.openfoam_bashrc and runner.bashrc_exists(self.settings.openfoam_bashrc, self.settings):
            return
        on_log(
            f"OpenFOAM bashrc not found at '{self.settings.openfoam_bashrc or '(none set)'}'; "
            "auto-detecting installation in WSL..."
        )
        detected = runner.find_openfoam_bashrc(self.settings)
        if detected is None:
            raise RuntimeError(
                "Could not find an OpenFOAM etc/bashrc in WSL. Set the path manually in the WSL / OpenFOAM settings box."
            )
        on_log(f"Using auto-detected OpenFOAM bashrc: {detected}")
        self.settings = replace(self.settings, openfoam_bashrc=detected)

    def available_processors(self) -> int:
        return runner.available_processors(self.settings)

    def run(self, commands: list[str], case_dir: Path, on_log: Callable[[str], None]) -> None:
        runner.run_commands(commands, case_dir, self.settings, on_log)


@dataclass
class NativeLinuxExecutionBackend:
    settings: NativeLinuxSettings

    @property
    def case_root(self) -> Path:
        return self.settings.case_root

    def ensure_ready(self, on_log: Callable[[str], None]) -> None:
        if self.settings.openfoam_bashrc and runner.bashrc_exists_native(self.settings.openfoam_bashrc):
            return
        on_log(
            f"OpenFOAM bashrc not found at '{self.settings.openfoam_bashrc or '(none set)'}'; auto-detecting..."
        )
        detected = runner.find_openfoam_bashrc_native()
        if detected is None:
            raise RuntimeError(
                "Could not find an OpenFOAM etc/bashrc on this host. Set the path manually in the settings box."
            )
        on_log(f"Using auto-detected OpenFOAM bashrc: {detected}")
        self.settings = replace(self.settings, openfoam_bashrc=detected)

    def available_processors(self) -> int:
        return runner.available_processors_native()

    def run(self, commands: list[str], case_dir: Path, on_log: Callable[[str], None]) -> None:
        runner.run_commands_native(commands, case_dir, self.settings, on_log)
