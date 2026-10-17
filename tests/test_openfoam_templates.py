"""OpenFOAM dictionary/field-file text builders: geometry math and expected patch/field
content, checked without needing an OpenFOAM install."""
from __future__ import annotations

import numpy as np
import pytest

from rocketcfd.openfoam import templates
from rocketcfd.openfoam.settings import GroundPlane, MeshSettings, SymmetryPlane

BODY_BOUNDS = (0.0, 4.0, -1.0, 1.0, 0.0, 1.5)


def test_domain_bounds_scale_with_body_length() -> None:
    settings = MeshSettings(upstream_lengths=2.0, downstream_lengths=3.0, side_lengths=1.0, top_lengths=1.0)
    domain = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None)
    xmin, xmax, ymin, ymax, zmin, zmax = domain
    body_length = BODY_BOUNDS[1] - BODY_BOUNDS[0]
    assert xmin == BODY_BOUNDS[0] - 2.0 * body_length
    assert xmax == BODY_BOUNDS[1] + 3.0 * body_length
    assert zmin == BODY_BOUNDS[4] - 1.0 * body_length
    assert zmax == BODY_BOUNDS[5] + 1.0 * body_length


def test_domain_bounds_unchanged_below_supersonic_mach() -> None:
    settings = MeshSettings(downstream_lengths=3.0)
    subsonic = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None, mach=0.8)
    baseline = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None, mach=0.0)
    assert subsonic[1] == baseline[1]


def test_domain_bounds_widens_downstream_for_supersonic_mach() -> None:
    settings = MeshSettings(downstream_lengths=3.0)
    baseline = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None, mach=0.0)
    supersonic = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None, mach=2.5)
    assert supersonic[1] > baseline[1]


def test_ground_effect_keeps_bottom_at_body_low_point() -> None:
    settings = MeshSettings()
    domain = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=GroundPlane(axis="z", side="min"))
    assert domain[4] == BODY_BOUNDS[4]


def test_ground_effect_supports_a_non_default_axis_and_side() -> None:
    settings = MeshSettings()
    domain = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=GroundPlane(axis="y", side="max"))
    assert domain[3] == BODY_BOUNDS[3]


def test_symmetry_plane_clips_axis_to_its_offset() -> None:
    settings = MeshSettings(side_lengths=1.0)
    domain = templates.domain_bounds(BODY_BOUNDS, settings, symmetry_planes=(SymmetryPlane(axis="y", offset=0.0),))
    assert domain[2] == 0.0


def test_two_symmetry_planes_quarter_the_domain() -> None:
    settings = MeshSettings(side_lengths=1.0, top_lengths=1.0)
    domain = templates.domain_bounds(
        BODY_BOUNDS, settings, symmetry_planes=(SymmetryPlane(axis="y", offset=0.0), SymmetryPlane(axis="z", offset=0.5))
    )
    assert domain[2] == 0.0
    assert domain[4] == 0.5


def test_symmetry_planes_reject_duplicate_axes() -> None:
    with pytest.raises(ValueError):
        templates.domain_bounds(
            BODY_BOUNDS, MeshSettings(), symmetry_planes=(SymmetryPlane(axis="y", offset=0.0), SymmetryPlane(axis="y", offset=0.2))
        )


def test_ground_plane_and_symmetry_plane_reject_shared_axis() -> None:
    with pytest.raises(ValueError):
        templates.domain_bounds(
            BODY_BOUNDS, MeshSettings(), ground_plane=GroundPlane(axis="y", side="min"),
            symmetry_planes=(SymmetryPlane(axis="y", offset=0.0),),
        )


def test_location_in_mesh_is_outside_body_bbox() -> None:
    settings = MeshSettings(upstream_lengths=2.0)
    domain = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None)
    location = templates.location_in_mesh(domain, BODY_BOUNDS, settings)
    assert location[0] < BODY_BOUNDS[0]
    assert domain[0] < location[0]


def test_location_in_mesh_clamps_into_a_symmetry_trimmed_domain() -> None:
    settings = MeshSettings(upstream_lengths=2.0, side_lengths=1.0)
    domain = templates.domain_bounds(BODY_BOUNDS, settings, symmetry_planes=(SymmetryPlane(axis="y", offset=0.5),))
    location = templates.location_in_mesh(domain, BODY_BOUNDS, settings)
    assert domain[2] < location[1] < domain[3]


def test_background_cell_counts_at_least_one() -> None:
    settings = MeshSettings(background_cell_count=1000)
    domain = templates.domain_bounds(BODY_BOUNDS, settings, ground_plane=None)
    counts = templates.background_cell_counts(domain, BODY_BOUNDS, settings)
    assert all(c >= 1 for c in counts)


def test_block_mesh_dict_ground_effect_splits_bottom_patch() -> None:
    domain = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    text = templates.block_mesh_dict(domain, (1, 1, 1), ground_plane=GroundPlane(axis="z", side="min"))
    assert "ground" in text
    assert "farField" in text
    assert "(0 3 2 1)" in text


def test_block_mesh_dict_symmetry_plane_adds_patch() -> None:
    domain = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    text = templates.block_mesh_dict(domain, (1, 1, 1), symmetry_planes=(SymmetryPlane(axis="y", offset=0.0),))
    assert "symmetryPlane" in text


def test_block_mesh_dict_two_symmetry_planes_add_two_patches() -> None:
    domain = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    text = templates.block_mesh_dict(
        domain, (1, 1, 1), symmetry_planes=(SymmetryPlane(axis="y", offset=0.0), SymmetryPlane(axis="z", offset=0.0))
    )
    assert text.count("symmetryPlane") == 2
    assert "symmetry_y" in text
    assert "symmetry_z" in text


def test_block_mesh_dict_no_ground_effect_has_single_patch() -> None:
    domain = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    text = templates.block_mesh_dict(domain, (1, 1, 1), ground_plane=None)
    assert "ground" not in text
    assert text.count("farField") == 1


def test_u_field_lists_wall_patches_and_freestream_value() -> None:
    text = templates.u_field(np.array([10.0, 0.0, 0.0]), ["body", "ground"])
    assert "body" in text
    assert "ground" in text
    assert "noSlip" in text
    assert "freestreamVelocity" in text
    assert "(10 0 0)" in text


def test_control_dict_incompressible_uses_rho_inf() -> None:
    text = templates.control_dict(
        "simpleFoam", 500, 100, forces_patches=["body"], rho_inf=1.225, cofr=np.array([1.0, 2.0, 3.0]), compressible=False,
    )
    assert "forces1" in text
    assert "rhoInf          1.225" in text
    assert "(1 2 3)" in text


def test_control_dict_compressible_uses_rho_field() -> None:
    text = templates.control_dict(
        "rhoSimpleFoam", 500, 100, forces_patches=["body"], cofr=np.array([1.0, 2.0, 3.0]), compressible=True,
    )
    assert "rho             rho;" in text
    assert "rhoInf" not in text


def test_control_dict_omits_functions_block_when_not_requested() -> None:
    text = templates.control_dict("simpleFoam", 1, 1)
    assert "functions" not in text


def test_control_dict_transient_adds_courant_control() -> None:
    text = templates.control_dict("rhoPimpleFoam", 1.0, 0.1, transient=True, max_courant=0.8)
    assert "adjustTimeStep  yes;" in text
    assert "maxCo           0.8;" in text


def test_thermophysical_properties_has_perfect_gas_block() -> None:
    text = templates.thermophysical_properties()
    assert "perfectGas" in text
    assert "sutherland" in text


def test_t_field_adiabatic_uses_zero_gradient() -> None:
    text = templates.t_field(288.15, ["body"], adiabatic_wall=True, wall_temperature=300.0)
    assert "zeroGradient" in text


def test_t_field_isothermal_uses_fixed_value() -> None:
    text = templates.t_field(288.15, ["body"], adiabatic_wall=False, wall_temperature=350.0)
    assert "value uniform 350" in text


def test_snappy_hex_mesh_dict_default_uses_relative_layer_sizing() -> None:
    text = templates.snappy_hex_mesh_dict(MeshSettings(), (0.0, 0.0, 0.0))
    assert "relativeSizes true;" in text
    assert "finalLayerThickness" in text
    assert "firstLayerThickness" not in text


def test_snappy_hex_mesh_dict_with_first_layer_thickness_uses_absolute_sizing() -> None:
    text = templates.snappy_hex_mesh_dict(MeshSettings(), (0.0, 0.0, 0.0), first_layer_thickness=2.5e-5)
    assert "relativeSizes false;" in text
    assert "firstLayerThickness     2.5e-05;" in text
    assert "finalLayerThickness" not in text


def test_snappy_hex_mesh_dict_without_feature_refinement_has_no_regions_block() -> None:
    text = templates.snappy_hex_mesh_dict(MeshSettings(), (0.0, 0.0, 0.0))
    assert "regions" not in text


def test_snappy_hex_mesh_dict_feature_refinement_adds_named_region_levels() -> None:
    text = templates.snappy_hex_mesh_dict(
        MeshSettings(), (0.0, 0.0, 0.0), feature_refinement={"fin": (4, 6), "nosecone": (3, 5)}
    )
    assert "fin { level (4 6); }" in text
    assert "nosecone { level (3 5); }" in text
