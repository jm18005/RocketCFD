"""Parametric rocket-part geometry generators."""
from __future__ import annotations

import numpy as np
import pytest

from rocketcfd.templates_geometry import (
    NOSECONE_CONIC,
    NOSECONE_OGIVE,
    NOSECONE_VON_KARMAN,
    REGION_BODY_TUBE,
    REGION_FIN,
    REGION_NOSECONE,
    assemble_rocket,
    assemble_rocket_labeled,
    body_tube,
    boattail,
    nosecone,
    trapezoidal_fin,
)


def test_body_tube_has_expected_length_and_radius() -> None:
    mesh = body_tube(length=2.0, diameter=0.3)
    bounds = mesh.bounds
    assert bounds[1][0] - bounds[0][0] == pytest.approx(2.0, abs=1e-6)
    radial_extent = max(bounds[1][1] - bounds[0][1], bounds[1][2] - bounds[0][2])
    assert radial_extent == pytest.approx(0.3, abs=1e-3)


@pytest.mark.parametrize("shape", [NOSECONE_CONIC, NOSECONE_OGIVE, NOSECONE_VON_KARMAN])
def test_nosecone_tip_is_pointed_and_base_matches_diameter(shape: str) -> None:
    mesh = nosecone(length=0.5, base_diameter=0.2, shape=shape)
    vertices = mesh.vertices
    tip_radii = np.linalg.norm(vertices[np.isclose(vertices[:, 0], 0.0)][:, 1:], axis=1)
    assert np.max(tip_radii) < 1e-6
    base_radii = np.linalg.norm(vertices[np.isclose(vertices[:, 0], 0.5)][:, 1:], axis=1)
    assert np.max(base_radii) == pytest.approx(0.1, abs=1e-3)


def test_nosecone_unknown_shape_raises() -> None:
    with pytest.raises(ValueError):
        nosecone(length=0.5, base_diameter=0.2, shape="not_a_shape")


def test_boattail_tapers_between_diameters() -> None:
    mesh = boattail(length=0.3, forward_diameter=0.3, aft_diameter=0.2)
    bounds = mesh.bounds
    assert bounds[1][0] - bounds[0][0] == pytest.approx(0.3, abs=1e-6)


def test_trapezoidal_fin_has_positive_volume_extent() -> None:
    fin = trapezoidal_fin(root_chord=0.15, tip_chord=0.05, span=0.08, sweep_distance=0.08, thickness=0.004)
    bounds = fin.bounds
    assert bounds[1][2] - bounds[0][2] == pytest.approx(0.004, abs=1e-6)


def test_assemble_rocket_places_parts_along_axis() -> None:
    nose = nosecone(length=0.5, base_diameter=0.2)
    body = body_tube(length=1.0, diameter=0.2)
    fin = trapezoidal_fin(root_chord=0.15, tip_chord=0.05, span=0.08, sweep_distance=0.08, thickness=0.004)
    rocket = assemble_rocket(nose, body, fins=[fin, fin.copy(), fin.copy()])
    bounds = rocket.bounds
    assert bounds[1][0] - bounds[0][0] > 1.4


def test_assemble_rocket_labeled_matches_unlabeled_geometry() -> None:
    nose = nosecone(length=0.5, base_diameter=0.2)
    body = body_tube(length=1.0, diameter=0.2)
    fin = trapezoidal_fin(root_chord=0.15, tip_chord=0.05, span=0.08, sweep_distance=0.08, thickness=0.004)
    rocket = assemble_rocket(nose, body, fins=[fin, fin.copy(), fin.copy()])
    labeled_rocket, face_regions = assemble_rocket_labeled(nose, body, fins=[fin, fin.copy(), fin.copy()])
    assert len(face_regions) == len(labeled_rocket.faces)
    assert len(labeled_rocket.faces) == len(rocket.faces)


def test_assemble_rocket_labeled_regions_cover_every_part() -> None:
    nose = nosecone(length=0.5, base_diameter=0.2)
    body = body_tube(length=1.0, diameter=0.2)
    fin = trapezoidal_fin(root_chord=0.15, tip_chord=0.05, span=0.08, sweep_distance=0.08, thickness=0.004)
    _rocket, face_regions = assemble_rocket_labeled(nose, body, fins=[fin, fin.copy()])
    assert set(face_regions) == {REGION_NOSECONE, REGION_BODY_TUBE, REGION_FIN}
