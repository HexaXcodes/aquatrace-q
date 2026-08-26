"""
GIS provider registry (Phases 12-13/24).

Rakesh's entire Phase 24 integration task is: obtain the real datasets,
set `REEF_DATA_PATH` / `MPA_DATA_PATH` / `GIS_ENABLED=true` in `.env`,
and restart. Nothing in `risk_service.py`, `priority_service.py`, or
any API route changes.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.gis.mpa_provider import GeoJSONMPAProvider, MPAProvider, NullMPAProvider
from app.gis.reef_provider import GeoJSONReefProvider, NullReefProvider, ReefProvider


@lru_cache
def get_reef_provider() -> ReefProvider:
    settings = get_settings()
    if not settings.GIS_ENABLED or not settings.REEF_DATA_PATH:
        return NullReefProvider()
    return GeoJSONReefProvider.from_path(settings.REEF_DATA_PATH)


@lru_cache
def get_mpa_provider() -> MPAProvider:
    settings = get_settings()
    if not settings.GIS_ENABLED or not settings.MPA_DATA_PATH:
        return NullMPAProvider()
    return GeoJSONMPAProvider.from_path(settings.MPA_DATA_PATH)


def reset_gis_registry_cache() -> None:
    """Test-only: clear cached providers so tests can inject fixture datasets."""
    get_reef_provider.cache_clear()
    get_mpa_provider.cache_clear()
