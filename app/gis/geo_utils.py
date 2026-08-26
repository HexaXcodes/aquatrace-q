"""Geodesic distance helper shared by ReefProvider/MPAProvider/CoordinateService.

Per spec section 44 ("Do NOT calculate distances using naive latitude/
longitude Euclidean distance"), every distance in metres reported by
this backend goes through `pyproj`'s WGS84 geodesic solver, not a raw
Pythagorean distance on lat/lon degrees.
"""

from __future__ import annotations

from pyproj import Geod
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

_WGS84_GEOD = Geod(ellps="WGS84")


def geodesic_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (ellipsoidal, WGS84) distance between two points, in metres."""
    _, _, distance_m = _WGS84_GEOD.inv(lon1, lat1, lon2, lat2)
    return float(distance_m)


def nearest_boundary_point(geometry: BaseGeometry, point: Point) -> tuple[float, float]:
    """Return (lon, lat) of the point on `geometry`'s boundary closest to
    `point`, found in unprojected lon/lat space (see the precision note
    in `ReefProvider`/`MPAProvider`)."""
    boundary = geometry.boundary if geometry.geom_type != "Point" else geometry
    nearest_on_boundary, _ = nearest_points(boundary, point)
    return nearest_on_boundary.x, nearest_on_boundary.y
