"""
Centralized application configuration.

All runtime configuration is read from environment variables (see
`.env.example`). Nothing here should be hardcoded per-deployment; the
values below are safe local-development defaults only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---------------------------------------------------
    APP_NAME: str = "AquaTrace-Q Backend"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"  # development | staging | production
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # --- Database --------------------------------------------------------
    # Full SQLAlchemy URL, e.g.
    # postgresql+psycopg2://aquatrace:aquatrace@localhost:5432/aquatrace
    DATABASE_URL: str = (
        "postgresql+psycopg2://aquatrace:aquatrace@localhost:5432/aquatrace"
    )
    DATABASE_ECHO: bool = False

    # --- Async task queue (only wired up once genuinely needed) ---------
    REDIS_URL: str | None = None

    # --- Storage ----------------------------------------------------------
    DATA_DIRECTORY: Path = Path("data")
    UPLOAD_DIRECTORY: Path = Path("uploads")
    OUTPUT_DIRECTORY: Path = Path("outputs")
    MODEL_DIRECTORY: Path = Path("models")

    # --- Upload constraints ------------------------------------------------
    MAX_UPLOAD_SIZE: int = 200 * 1024 * 1024  # 200 MB
    # Comma-separated string, not list[str]/tuple[str, ...]: pydantic-settings
    # tries to JSON-decode complex-typed fields straight from the .env value
    # before any validator runs, which breaks on plain comma-separated input.
    ALLOWED_SONAR_EXTENSIONS: str = "png,jpg,jpeg,tif,tiff"

    # --- CORS ---------------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- GIS (wired up in later phases; kept here so .env stays stable) -----
    REEF_DATA_PATH: Path | None = None
    MPA_DATA_PATH: Path | None = None
    GIS_ENABLED: bool = False

    # --- ML / QML ------------------------------------------------------------
    ML_MODEL_VERSION: str | None = None
    QML_ENABLED: bool = True
    QML_FEATURE_DIMENSIONS: int = 4  # PCA target dimensionality before the quantum feature map
    ENABLE_SHIPWRECK_DETECTOR: bool = False  # Disabled by default for general debris/gear survey triage

    # --- Uncertainty (Phase 10) ------------------------------------------------
    UNCERTAINTY_HIGH_THRESHOLD: float = 0.66  # normalized entropy >= this -> HIGH
    UNCERTAINTY_MEDIUM_THRESHOLD: float = 0.33  # >= this -> MEDIUM, else LOW

    # --- Risk engine (Phase 14) -- weights must sum to 100 -----------------------
    RISK_WEIGHT_DEBRIS_TYPE: float = 30.0
    RISK_WEIGHT_REEF_PROXIMITY: float = 30.0
    RISK_WEIGHT_PROTECTED_AREA: float = 15.0
    RISK_WEIGHT_SIZE: float = 15.0
    RISK_WEIGHT_CONFIDENCE: float = 10.0
    RISK_WEIGHTS_VERSION: str = "v1"

    RISK_LEVEL_CRITICAL_THRESHOLD: float = 85.0
    RISK_LEVEL_HIGH_THRESHOLD: float = 60.0
    RISK_LEVEL_MEDIUM_THRESHOLD: float = 30.0

    # --- Priority engine (Phase 15) ----------------------------------------------
    PRIORITY_VERIFY_NOW_RISK_THRESHOLD: float = 75.0
    PRIORITY_VERIFY_NEXT_RISK_THRESHOLD: float = 45.0
    PRIORITY_IGNORE_CONFIDENCE_THRESHOLD: float = 0.85  # natural seabed, high confidence

    # --- Mission planning (Phase 16) ----------------------------------------------
    MISSION_DEFAULT_VEHICLE_SPEED_MPS: float = 1.0  # ~2 knots, a slow survey AUV

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_sonar_extensions_tuple(self) -> tuple[str, ...]:
        return tuple(
            ext.strip().lower().lstrip(".") for ext in self.ALLOWED_SONAR_EXTENSIONS.split(",") if ext.strip()
        )

    def ensure_directories(self) -> None:
        """Create storage directories on startup if they don't already exist."""
        for directory in (
            self.DATA_DIRECTORY,
            self.UPLOAD_DIRECTORY,
            self.OUTPUT_DIRECTORY,
            self.MODEL_DIRECTORY,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is only parsed once per process)."""
    return Settings()
