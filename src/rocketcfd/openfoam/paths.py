"""Windows <-> WSL path translation, assuming the default `/mnt/<drive>` mount layout."""
from __future__ import annotations

from pathlib import Path


def to_wsl_path(path: Path) -> str:
    """Path.resolve() always yields a drive-rooted absolute path on Windows, so the
    drive letter is always present here."""
    resolved = Path(path).resolve()
    drive_letter = resolved.drive[0].lower()
    remainder = "/".join(resolved.parts[1:])
    return f"/mnt/{drive_letter}/{remainder}" if remainder else f"/mnt/{drive_letter}"
