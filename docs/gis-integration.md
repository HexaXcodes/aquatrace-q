# GIS Integration Guide (for Rakesh)

`app/gis/reef_provider.py` and `app/gis/mpa_provider.py` already implement
real spatial queries (point-in-polygon via Shapely, distance via a proper
WGS84 geodesic calculation via pyproj — never naive lat/lon Euclidean
distance). What's missing is the real datasets.

## Loading a real dataset

1. Obtain the reef dataset (intended source: **UNEP-WCMC Global Distribution
   of Coral Reefs**) and the MPA dataset (e.g. **WDPA**).
2. Convert to GeoJSON `FeatureCollection` of polygons if not already in that
   format. Each feature's `properties` should include:
   - Reef: `id`, `name` (optional), `habitat_type` or `ecosystem` (optional)
   - MPA: `id`, `name` (optional), `protection_level` or `iucn_category` (optional)
3. Set in `.env`:
   ```
   GIS_ENABLED=true
   REEF_DATA_PATH=/path/to/reefs.geojson
   MPA_DATA_PATH=/path/to/mpas.geojson
   ```
4. Restart the backend. `app/gis/registry.py` picks up the real
   `GeoJSONReefProvider`/`GeoJSONMPAProvider` automatically — nothing else
   changes.

## Extending to Shapefile / GeoPackage / PostGIS

`app/gis/dataset_loader.py`'s `load_polygon_features()` is the only place
that knows the on-disk format. It currently supports GeoJSON only (kept
deliberately light — no GeoPandas/Fiona/GDAL dependency). To add Shapefile
or GeoPackage support, extend that one function to return the same
`list[PolygonFeature]` shape; `ReefProvider`/`MPAProvider` don't need to
change. Moving the query itself into PostGIS (`ST_Distance`,
`ST_Contains`) instead of in-process Shapely is the natural next step once
the dataset is large enough that loading it into memory per-process stops
being practical — same interface, different backing implementation.

## Honesty guarantee

If `GIS_ENABLED=false` or a path isn't set, `NullReefProvider`/
`NullMPAProvider` are used and every query returns
`GISStatus.NOT_CONFIGURED` with every numeric field `null` — risk/priority
scoring treats that as "this factor contributes 0", not "target is far from
any reef". See `tests/test_gis.py` and `app/services/risk_service.py`.

## Precision note

Nearest-boundary-point search happens in unprojected lon/lat space (fast,
simple, adequate at reef/MPA scale — tens to low thousands of metres); the
final reported distance is then computed with a real geodesic calculation
between that point and the query point. This is not accurate at continental
scale, which is out of scope for reef/MPA proximity.
