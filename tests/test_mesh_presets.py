"""Mesh density presets (coarse/medium/fine)."""
from __future__ import annotations

import pytest

from rocketcfd.openfoam.settings import (
    MESH_PRESET_COARSE,
    MESH_PRESET_FINE,
    MESH_PRESET_MEDIUM,
    MeshSettings,
    mesh_settings_for_preset,
)


def test_medium_preset_matches_meshsettings_defaults() -> None:
    preset = mesh_settings_for_preset(MESH_PRESET_MEDIUM)
    defaults = MeshSettings()
    assert preset.background_cell_count == defaults.background_cell_count
    assert preset.surface_refinement_max == defaults.surface_refinement_max
    assert preset.n_boundary_layers == defaults.n_boundary_layers


def test_fine_preset_is_finer_than_coarse() -> None:
    coarse = mesh_settings_for_preset(MESH_PRESET_COARSE)
    fine = mesh_settings_for_preset(MESH_PRESET_FINE)
    assert fine.surface_refinement_max > coarse.surface_refinement_max
    assert fine.background_cell_count > coarse.background_cell_count
    assert fine.n_boundary_layers > coarse.n_boundary_layers
    assert fine.target_y_plus < coarse.target_y_plus


def test_preset_returns_an_independent_copy() -> None:
    first = mesh_settings_for_preset(MESH_PRESET_COARSE)
    first.feature_refinement_levels["fin"] = (1, 2)
    second = mesh_settings_for_preset(MESH_PRESET_COARSE)
    assert second.feature_refinement_levels == {}


def test_unknown_preset_raises() -> None:
    with pytest.raises(ValueError):
        mesh_settings_for_preset("ultra")
