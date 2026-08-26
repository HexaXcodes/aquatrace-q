"""
Minimal GeoJSON polygon-dataset loader shared by `ReefProvider` and
`MPAProvider`.

Deliberately dependency-light (stdlib `json` + `shapely`, no GeoPandas/
Fiona/GDAL) since the only thing either provider needs is "a list of
named polygons" -- GeoPandas would add a much heavier native-dependency
footprint for no functional gain at this scale. `GeoPackage`/`Shapefile`
support (mentioned in spec sections 20/21) is not implemented here: only
GeoJSON, since that's what's actually been exercised. Extending
`load_polygon_features` to accept a Shapefile/GeoPackage path is a
self-contained change -- nothing in `ReefProvider`/`MPAProvider` needs
to know the difference once it gets back the same `PolygonFeature` list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


@dataclass(slots=True)
class PolygonFeature:
    feature_id: str
    name: str | None
    geometry: BaseGeometry
    properties: dict


def load_polygon_features(path: Path) -> list[PolygonFeature]:
    """Load a GeoJSON FeatureCollection of polygons/multipolygons.

    Raises `ValueError` on anything that isn't a well-formed
    FeatureCollection -- callers should treat that as a configuration
    error (surfaced at startup/log time), not silently fall back to
    "no dataset".
    """
    if not path.exists():
        raise ValueError(f"GIS dataset not found at '{path}'.")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if payload.get("type") != "FeatureCollection":
        raise ValueError(f"'{path}' is not a GeoJSON FeatureCollection.")

    features: list[PolygonFeature] = []
    for index, feature in enumerate(payload.get("features", [])):
        geometry = shape(feature["geometry"])
        properties = feature.get("properties", {}) or {}
        feature_id = str(properties.get("id", index))
        name = properties.get("name")
        features.append(
            PolygonFeature(feature_id=feature_id, name=name, geometry=geometry, properties=properties)
        )

    return features
