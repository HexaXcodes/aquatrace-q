from __future__ import annotations

import json

from app.gis.mpa_provider import GeoJSONMPAProvider, NullMPAProvider
from app.gis.reef_provider import GeoJSONReefProvider, NullReefProvider


def _tiny_reef_geojson(tmp_path):
    # A small square polygon "reef" roughly 100m x 100m near (12.90, 74.80).
    path = tmp_path / "reef.geojson"
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "reef-1", "name": "Test Reef", "habitat_type": "fringing_reef"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [74.800, 12.900],
                            [74.801, 12.900],
                            [74.801, 12.901],
                            [74.800, 12.901],
                            [74.800, 12.900],
                        ]
                    ],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload))
    return path


def test_null_reef_provider_returns_not_configured() -> None:
    provider = NullReefProvider()
    context = provider.get_context(12.9, 74.8)
    assert context.status.value == "NOT_CONFIGURED"
    assert context.distance_m is None
    assert context.inside_reef is None


def test_geojson_reef_provider_inside_and_outside(tmp_path) -> None:
    path = _tiny_reef_geojson(tmp_path)
    provider = GeoJSONReefProvider.from_path(path, is_test_fixture=True)

    inside = provider.get_context(12.9005, 74.8005)  # well within the square
    assert inside.status.value == "TEST_FIXTURE"
    assert inside.inside_reef is True
    assert inside.distance_m == 0.0
    assert inside.reef_id == "reef-1"
    assert inside.habitat_context == "fringing_reef"

    outside = provider.get_context(12.95, 74.85)  # clearly outside
    assert outside.inside_reef is False
    assert outside.distance_m > 0


def test_null_mpa_provider_returns_not_configured() -> None:
    provider = NullMPAProvider()
    context = provider.get_context(12.9, 74.8)
    assert context.status.value == "NOT_CONFIGURED"
    assert context.inside_mpa is None


def test_geodesic_distance_is_realistic() -> None:
    from app.gis.geo_utils import geodesic_distance_m

    # Roughly 111km per degree of latitude near the equator.
    distance = geodesic_distance_m(0.0, 0.0, 1.0, 0.0)
    assert 110_000 < distance < 112_000
