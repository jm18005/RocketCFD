"""Content-hash based case cache: skips re-running a condition already solved with the
same geometry, mesh, and solver settings."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

MANIFEST_FILENAME = "rocketcfd_cache_manifest.json"


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, np.ndarray):
        # Hashing raw bytes avoids building a Python list of (potentially hundreds of
        # thousands of) floats just to round-trip it through json.dumps.
        return {"shape": value.shape, "dtype": str(value.dtype), "sha256": hashlib.sha256(value.tobytes()).hexdigest()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return round(value, 12)
    return value


def compute_case_hash(*parts: Any) -> str:
    """Stable hash over any mix of dataclasses/dicts/arrays/primitives, used as the cache
    key for one (geometry, flow condition, mesh settings, solver settings) combination."""
    payload = json.dumps([_to_jsonable(part) for part in parts], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class CaseCache:
    """Persists case_hash -> run directory name in MANIFEST_FILENAME under case_root, so a
    repeated sweep (same geometry/conditions/settings) can skip cases already solved."""

    def __init__(self, case_root: Path) -> None:
        self.case_root = case_root
        self._manifest_path = case_root / MANIFEST_FILENAME
        self._manifest: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not self._manifest_path.exists():
            return {}
        return json.loads(self._manifest_path.read_text())

    def lookup(self, case_hash: str) -> Path | None:
        run_dir_name = self._manifest.get(case_hash)
        if run_dir_name is None:
            return None
        run_dir = self.case_root / run_dir_name
        return run_dir if run_dir.exists() else None

    def record(self, case_hash: str, run_dir: Path) -> None:
        self._manifest[case_hash] = run_dir.name
        self._manifest_path.write_text(json.dumps(self._manifest, indent=2, sort_keys=True))
