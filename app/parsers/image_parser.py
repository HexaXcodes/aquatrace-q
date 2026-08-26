"""
Parses plain raster images (PNG/JPEG/TIFF) standing in for sonar
waterfall exports during development.

This deliberately extracts *only* pixel dimensions. A PNG/JPEG has no
sonar acquisition metadata (CRS, meters-per-pixel, frequency, sensor) --
claiming otherwise would violate spec section 7 ("Do NOT pretend PNG
contains sonar metadata"). Any of that metadata the operator actually
has is supplied explicitly via `SurveyUploadMetadata` at upload time.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.exceptions import InvalidSonarFileError
from app.parsers.base import ParsedSonarFile, SonarParser


class ImageSonarParser(SonarParser):
    def parse(self, file_path: Path) -> ParsedSonarFile:
        try:
            with Image.open(file_path) as img:
                img.verify()  # raises if the file is truncated/corrupt

            # Re-open after verify(): verify() leaves the file object unusable.
            with Image.open(file_path) as img:
                width, height = img.size
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidSonarFileError(
                f"Could not read '{file_path.name}' as an image.",
                file_path=str(file_path),
            ) from exc

        return ParsedSonarFile(width=width, height=height)
