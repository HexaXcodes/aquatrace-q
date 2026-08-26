"""
Coordinate service (Phase 11).

Converts a target's pixel bbox center into a latitude/longitude when
the survey has enough real metadata to do so (`origin_latitude`,
`origin_longitude`, `meters_per_pixel`) -- otherwise returns `None`
rather than guessing.

Transform convention: pixel (0, 0) is the survey's `origin_latitude` /
`origin_longitude`; +x (columns) is East, +y (rows) is South, which
matches how a side-scan sonar waterfall is conventionally laid out
(along-track distance increasing downward). This is applied as two
sequential WGS84 geodesic forward solves (south then east) via pyproj
-- not a flat-earth Pythagorean approximation -- so it stays accurate
away from the equator and at higher latitudes.

This is a first-order local approximation suitable for a single sonar
survey's footprint (metres to a few km): it does not account for
sensor heading/attitude or along-track navigation drift, which would
require real per-ping navigation data (an XTF file, not a PNG) to
correct for -- see `app/parsers/xtf_parser.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import Geod

from app.models.enums import CoordinateSource
from app.models.survey import Survey
from app.models.target import Target

_GEOD = Geod(ellps="WGS84")

_AZIMUTH_SOUTH = 180.0
_AZIMUTH_EAST = 90.0


@dataclass(slots=True)
class GeolocationResult:
    latitude: float | None
    longitude: float | None
    source: CoordinateSource | None
    note: str


def _bbox_center_px(bbox: list[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def geolocate_target(survey: Survey, target: Target) -> GeolocationResult:
    if target.bbox is None:
        return GeolocationResult(None, None, None, "Target has no bbox to geolocate.")

    if survey.origin_latitude is None or survey.origin_longitude is None:
        return GeolocationResult(
            None, None, None, "Survey has no origin coordinates configured."
        )
    if not survey.meters_per_pixel:
        return GeolocationResult(
            None, None, None, "Survey has no meters_per_pixel configured."
        )

    x_px, y_px = _bbox_center_px(target.bbox)
    south_m = y_px * survey.meters_per_pixel
    east_m = x_px * survey.meters_per_pixel

    lon0, lat0 = survey.origin_longitude, survey.origin_latitude
    lon1, lat1, _ = _GEOD.fwd(lon0, lat0, _AZIMUTH_SOUTH, south_m)
    lon2, lat2, _ = _GEOD.fwd(lon1, lat1, _AZIMUTH_EAST, east_m)

    return GeolocationResult(
        latitude=round(lat2, 7),
        longitude=round(lon2, 7),
        source=CoordinateSource.SURVEY_TRANSFORM,
        note="Derived from survey origin + meters_per_pixel (pixel->geodesic transform).",
    )
