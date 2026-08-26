"""
Sonar file parser abstraction.

`get_parser_for_extension` is the only entry point services should use;
it hides which concrete parser handles a given file extension so that
adding a new sonar format never requires touching `survey_service.py`.
"""

from __future__ import annotations

from app.parsers.base import ParsedSonarFile, SonarParser
from app.parsers.image_parser import ImageSonarParser
from app.parsers.xtf_parser import XTFParser

_PARSERS: dict[str, SonarParser] = {
    "png": ImageSonarParser(),
    "jpg": ImageSonarParser(),
    "jpeg": ImageSonarParser(),
    "tif": ImageSonarParser(),
    "tiff": ImageSonarParser(),
    "xtf": XTFParser(),
}


def get_parser_for_extension(extension: str) -> SonarParser:
    ext = extension.lower().lstrip(".")
    try:
        return _PARSERS[ext]
    except KeyError as exc:
        raise ValueError(f"No sonar parser registered for extension '.{ext}'") from exc


__all__ = ["ParsedSonarFile", "SonarParser", "get_parser_for_extension"]
