"""Automates installing WSL2 + OpenFOAM (Windows) or OpenFOAM alone (native Linux), and
detects which platform this process is running on."""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

from rocketcfd.openfoam import runner
from rocketcfd.openfoam.settings import WslSettings

DEFAULT_UBUNTU_DISTRO = "Ubuntu"
DEFAULT_OPENFOAM_APT_PACKAGE = "openfoam2306-default"


def is_windows_host() -> bool:
    return sys.platform.startswith("win")


def is_linux_host() -> bool:
    return sys.platform.startswith("linux")


def openfoam_apt_install_script(package: str = DEFAULT_OPENFOAM_APT_PACKAGE) -> str:
    """Adds the openfoam.org apt repo and installs OpenFOAM, per
    https://openfoam.org/download/ubuntu/."""
    return (
        "set -e; "
        "curl -s https://dl.openfoam.org/gpg.key | sudo apt-key add -; "
        "sudo add-apt-repository -y http://dl.openfoam.org/ubuntu; "
        "sudo apt-get update; "
        f"sudo apt-get install -y {package}"
    )


def install_wsl_distro(on_line: Callable[[str], None], distro: str = DEFAULT_UBUNTU_DISTRO) -> None:
    """Installs WSL2 plus a Linux distro via `wsl --install`. Windows-only: requires a
    reboot on first-ever WSL install before the distro is usable."""
    if not is_windows_host():
        raise RuntimeError("install_wsl_distro only applies on Windows.")
    runner.stream_process(["wsl.exe", "--install", "-d", distro], on_line, f"wsl --install -d {distro}")


def install_openfoam_in_wsl(wsl_settings: WslSettings, on_line: Callable[[str], None]) -> None:
    if not is_windows_host():
        raise RuntimeError("install_openfoam_in_wsl only applies on Windows (targets a WSL distro).")
    script = openfoam_apt_install_script()
    command = [*runner.wsl_command_prefix(wsl_settings), "--", "bash", "-lc", script]
    runner.stream_process(command, on_line, "install OpenFOAM in WSL")


def install_openfoam_native(on_line: Callable[[str], None]) -> None:
    if not is_linux_host():
        raise RuntimeError("install_openfoam_native only applies on Linux.")
    script = openfoam_apt_install_script()
    runner.stream_process(["bash", "-lc", script], on_line, "install OpenFOAM")


def wsl_available() -> bool:
    if not is_windows_host():
        return False
    try:
        completed = subprocess.run(["wsl.exe", "--status"], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
