"""
`SonarParser` abstraction (spec section 7).

Every concrete parser turns a file on disk into a `ParsedSonarFile`. The
fields on `ParsedSonarFile` mirror the nullable metadata columns on
`Survey`: a parser fills in what it can genuinely read from the file and
leaves the rest `None` -- it must never guess.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ParsedSonarFile:
    width: int | None
    height: int | None
    coordinate_reference_system: str | None = None
    origin_latitude: float | None = None
    origin_longitude: float | None = None
    meters_per_pixel: float | None = None
    depth_min: float | None = None
    depth_max: float | None = None
    sonar_frequency: float | None = None
    sensor_name: str | None = None


class SonarParser(abc.ABC):
    """Interface every sonar file parser must implement."""

    @abc.abstractmethod
    def parse(self, file_path: Path) -> ParsedSonarFile:
        """Read whatever genuine metadata the file format provides.

        Implementations must raise `app.core.exceptions.InvalidSonarFileError`
        (not a bare exception) if the file cannot be read as the expected
        format.
        """
        raise NotImplementedError
