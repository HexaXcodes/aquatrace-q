"""
XTF (eXtended Triton Format) sonar file parser.

XTF is the native output format of most towfish/AUV side-scan sonar
systems and carries real navigation, frequency, and per-ping metadata --
exactly what a PNG/JPEG cannot provide. It is NOT implemented in Phases
1-5: there is no reliable, license-clean XTF reader available to wire up
in this timeframe, and spec section 7 is explicit that we should expose
the interface and document the limitation rather than fake it.

The class is registered in `app/parsers/__init__.py` against the `.xtf`
extension so that:
  - the API already accepts the idea of an XTF upload without any
    survey_service changes once a real reader lands, and
  - attempting one today fails loudly and specifically, instead of
    silently being treated as a corrupt image.

To implement this later: parse the XTF file header + ping headers
(typically via `pyxtf` or a custom binary reader), and populate
`meters_per_pixel`, `sonar_frequency`, `origin_latitude/longitude`, and
`coordinate_reference_system` from the real navigation packets.
"""

from __future__ import annotations

from pathlib import Path

from app.parsers.base import ParsedSonarFile, SonarParser


class XTFParser(SonarParser):
    def parse(self, file_path: Path) -> ParsedSonarFile:
        raise NotImplementedError(
            "XTF parsing is not implemented yet. AquaTrace-Q Phases 1-5 "
            "support PNG/JPG/JPEG/TIFF only; the .xtf extension is "
            "registered so the real parser can be dropped in later "
            "without changing survey_service.py or the API layer."
        )
