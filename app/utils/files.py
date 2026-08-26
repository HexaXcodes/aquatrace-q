"""
Small, dependency-free filesystem helpers shared by services.

Kept deliberately paranoid: everything here exists to close off a
specific class of bug (path traversal, unbounded reads), not to be
clever.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(raw_filename: str) -> str:
    """
    Collapse an arbitrary client-supplied filename into something safe to
    join onto a server-side path.

    Strips directory components entirely (so `../../etc/passwd` becomes
    `passwd`), normalizes unicode, and replaces anything outside
    `[A-Za-z0-9._-]` with `_`. A short random suffix is added to avoid
    collisions between uploads that happen to share a filename.
    """
    name = Path(raw_filename).name  # drop any directory components
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = _SAFE_CHARS.sub("_", name).strip("._") or "upload"

    stem, _, suffix = name.rpartition(".")
    unique = uuid.uuid4().hex[:8]
    if stem:
        return f"{stem}_{unique}.{suffix}" if suffix else f"{name}_{unique}"
    return f"{name}_{unique}"


def extension_of(filename: str) -> str:
    """Return the lowercase extension without the leading dot, or ''."""
    return Path(filename).suffix.lower().lstrip(".")


def resolve_within(base_directory: Path, *parts: str) -> Path:
    """
    Join `parts` onto `base_directory` and guarantee the result is still
    inside it (defense in depth against path traversal even though
    `sanitize_filename` should already prevent it).
    """
    base = base_directory.resolve()
    candidate = base.joinpath(*parts).resolve()
    if base not in candidate.parents and candidate != base:
        raise ValueError(f"Resolved path '{candidate}' escapes base directory '{base}'")
    return candidate
