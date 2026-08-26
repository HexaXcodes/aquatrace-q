"""
Regression test for a pydantic-settings gotcha.

Complex-typed fields (list[str], tuple[str, ...]) get JSON-decoded straight
from the environment/.env value before any `mode="before"` validator runs.
A plain comma-separated value like "png,jpg,jpeg" then raises a
SettingsError instead of reaching a splitter validator. This bit us for
real: an empty .env masked it during development, and it only surfaced once
CORS_ORIGINS/ALLOWED_SONAR_EXTENSIONS had actual values set.

ALLOWED_SONAR_EXTENSIONS and CORS_ORIGINS must stay plain `str` fields on
Settings, parsed on access via the allowed_sonar_extensions_tuple /
cors_origins_list properties -- not list[str]/tuple[str, ...] fields.
"""

from __future__ import annotations

from app.core.config import Settings


def test_settings_loads_comma_separated_env_vars(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example,http://b.example")
    monkeypatch.setenv("ALLOWED_SONAR_EXTENSIONS", "png,jpg,jpeg")

    settings = Settings(_env_file=None)

    assert settings.cors_origins_list == ["http://a.example", "http://b.example"]
    assert settings.allowed_sonar_extensions_tuple == ("png", "jpg", "jpeg")


def test_allowed_sonar_extensions_normalizes_case_dots_and_whitespace(monkeypatch):
    monkeypatch.setenv("ALLOWED_SONAR_EXTENSIONS", " .PNG , JPG ,tiff ")

    settings = Settings(_env_file=None)

    assert settings.allowed_sonar_extensions_tuple == ("png", "jpg", "tiff")


def test_cors_origins_strips_whitespace_and_drops_empties(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " http://a.example ,, http://b.example ")

    settings = Settings(_env_file=None)

    assert settings.cors_origins_list == ["http://a.example", "http://b.example"]
