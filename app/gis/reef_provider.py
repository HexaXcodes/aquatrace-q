"""
`ReefProvider` (Phase 12).

`GeoJSONReefProvider` is a real, working spatial-query implementation
(point-in-polygon via Shapely, distance via geodesic WGS84 calculation)
-- not a stub. It is intended to be pointed at the UNEP-WCMC Global
Distribution of Coral Reefs dataset (spec section 20), converted to
GeoJSON, via `REEF_DATA_PATH`.

If `REEF_DATA_PATH`/`GIS_ENABLED` are not configured, `NullReefProvider`
is used instead and every query returns `GISStatus.NOT_CONFIGURED` with
every numeric field `None` -- reef proximity is never guessed.

Rakesh's integration work for Phase 24 is exactly: obtain the real
reef dataset, convert it to GeoJSON (or extend `dataset_loader.py` for
Shapefile/GeoPackage/PostGIS), and set `REEF_DATA_PATH`/`GIS_ENABLED`.
Nothing in `risk_service.py` or `priority_service.py` changes.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Point

from app.gis.dataset_loader import PolygonFeature, load_polygon_features
from app.gis.geo_utils import geodesic_distance_m, nearest_boundary_point
from app.models.enums import GISStatus


@dataclass(slots=True)
class ReefContext:
    status: GISStatus
    reef_id: str | None = None
    distance_m: float | None = None
    inside_reef: bool | None = None
    habitat_context: str | None = None


class ReefProvider(abc.ABC):
    @abc.abstractmethod
    def get_context(self, latitude: float, longitude: float) -> ReefContext: ...

    def get_nearest_reef(self, latitude: float, longitude: float) -> str | None:
        return self.get_context(latitude, longitude).reef_id

    def get_distance_to_reef(self, latitude: float, longitude: float) -> float | None:
        return self.get_context(latitude, longitude).distance_m

    def is_inside_reef(self, latitude: float, longitude: float) -> bool | None:
        return self.get_context(latitude, longitude).inside_reef

    def get_habitat_context(self, latitude: float, longitude: float) -> str | None:
        return self.get_context(latitude, longitude).habitat_context


class NullReefProvider(ReefProvider):
    """Used whenever no reef dataset is configured. Never fabricates a distance."""

    def get_context(self, latitude: float, longitude: float) -> ReefContext:
        return ReefContext(status=GISStatus.NOT_CONFIGURED)


class GeoJSONReefProvider(ReefProvider):
    """
    Real spatial queries against a GeoJSON polygon dataset.

    Note on precision: nearest-boundary-point search is performed in
    unprojected lon/lat space (via Shapely), then the resulting point
    pair is measured with a proper WGS84 geodesic calculation. For
    reef-sized polygons (metres to a few km) this planar-search /
    geodesic-measure split introduces negligible error; it is not
    accurate at continental scale, which is out of scope here.
    """

    def __init__(self, features: list[PolygonFeature], *, is_test_fixture: bool = False) -> None:
        self._features = features
        self._status_when_found = GISStatus.TEST_FIXTURE if is_test_fixture else GISStatus.OK

    @classmethod
    def from_path(cls, path: Path, *, is_test_fixture: bool = False) -> "GeoJSONReefProvider":
        return cls(load_polygon_features(path), is_test_fixture=is_test_fixture)

    def get_context(self, latitude: float, longitude: float) -> ReefContext:
        if not self._features:
            return ReefContext(status=GISStatus.NOT_CONFIGURED)

        point = Point(longitude, latitude)
        best: tuple[PolygonFeature, float, bool] | None = None

        for feature in self._features:
            inside = feature.geometry.contains(point)
            if inside:
                distance_m = 0.0
            else:
                nearest_lon, nearest_lat = nearest_boundary_point(feature.geometry, point)
                distance_m = geodesic_distance_m(latitude, longitude, nearest_lat, nearest_lon)

            if best is None or distance_m < best[1]:
                best = (feature, distance_m, inside)

        assert best is not None
        feature, distance_m, inside = best
        habitat = feature.properties.get("habitat_type") or feature.properties.get("ecosystem")

        return ReefContext(
            status=self._status_when_found,
            reef_id=feature.feature_id,
            distance_m=round(distance_m, 2),
            inside_reef=inside,
            habitat_context=habitat,
        )
