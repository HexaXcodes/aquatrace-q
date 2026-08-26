"""
`MPAProvider` (Phase 13) -- structurally identical to `ReefProvider`,
kept as a separate class because reef and MPA datasets are genuinely
different sources (WDPA for MPAs vs UNEP-WCMC for reefs) with different
attribute schemas (`mpa_name`/`protection_level` vs `habitat_type`).
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
class MPAContext:
    status: GISStatus
    mpa_id: str | None = None
    mpa_name: str | None = None
    distance_m: float | None = None
    inside_mpa: bool | None = None
    protection_context: str | None = None


class MPAProvider(abc.ABC):
    @abc.abstractmethod
    def get_context(self, latitude: float, longitude: float) -> MPAContext: ...

    def is_inside_mpa(self, latitude: float, longitude: float) -> bool | None:
        return self.get_context(latitude, longitude).inside_mpa

    def nearest_mpa(self, latitude: float, longitude: float) -> str | None:
        return self.get_context(latitude, longitude).mpa_id

    def get_mpa_context(self, latitude: float, longitude: float) -> MPAContext:
        return self.get_context(latitude, longitude)


class NullMPAProvider(MPAProvider):
    def get_context(self, latitude: float, longitude: float) -> MPAContext:
        return MPAContext(status=GISStatus.NOT_CONFIGURED)


class GeoJSONMPAProvider(MPAProvider):
    def __init__(self, features: list[PolygonFeature], *, is_test_fixture: bool = False) -> None:
        self._features = features
        self._status_when_found = GISStatus.TEST_FIXTURE if is_test_fixture else GISStatus.OK

    @classmethod
    def from_path(cls, path: Path, *, is_test_fixture: bool = False) -> "GeoJSONMPAProvider":
        return cls(load_polygon_features(path), is_test_fixture=is_test_fixture)

    def get_context(self, latitude: float, longitude: float) -> MPAContext:
        if not self._features:
            return MPAContext(status=GISStatus.NOT_CONFIGURED)

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
        protection = feature.properties.get("protection_level") or feature.properties.get("iucn_category")

        return MPAContext(
            status=self._status_when_found,
            mpa_id=feature.feature_id,
            mpa_name=feature.name,
            distance_m=round(distance_m, 2),
            inside_mpa=inside,
            protection_context=protection,
        )
