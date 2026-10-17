"""Case-hash stability and the on-disk cache manifest."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from rocketcfd.caching import CaseCache, compute_case_hash
from rocketcfd.flow import FlowCondition


def test_hash_is_stable_for_equal_inputs() -> None:
    condition_a = FlowCondition(name="a", velocity=100.0, alpha_deg=5.0, beta_deg=0.0)
    condition_b = FlowCondition(name="a", velocity=100.0, alpha_deg=5.0, beta_deg=0.0)
    assert compute_case_hash(condition_a) == compute_case_hash(condition_b)


def test_hash_changes_with_different_inputs() -> None:
    condition_a = FlowCondition(name="a", velocity=100.0, alpha_deg=5.0, beta_deg=0.0)
    condition_b = FlowCondition(name="a", velocity=101.0, alpha_deg=5.0, beta_deg=0.0)
    assert compute_case_hash(condition_a) != compute_case_hash(condition_b)


def test_hash_handles_numpy_arrays() -> None:
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.0, 3.0])
    assert compute_case_hash(a) == compute_case_hash(b)


def test_cache_lookup_missing_returns_none(tmp_path: Path) -> None:
    cache = CaseCache(tmp_path)
    assert cache.lookup("nonexistent") is None


def test_cache_record_and_lookup_round_trip(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_000"
    run_dir.mkdir()
    cache = CaseCache(tmp_path)
    cache.record("abc123", run_dir)

    reloaded = CaseCache(tmp_path)
    assert reloaded.lookup("abc123") == run_dir


def test_cache_lookup_returns_none_if_dir_deleted(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_000"
    run_dir.mkdir()
    cache = CaseCache(tmp_path)
    cache.record("abc123", run_dir)
    run_dir.rmdir()
    assert cache.lookup("abc123") is None
