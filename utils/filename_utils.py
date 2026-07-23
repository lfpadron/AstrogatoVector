"""Safe download filename helpers."""

from __future__ import annotations

import re

_RESERVED_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SPACE_RE = re.compile(r"\s+")
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def sanitize_filename(value: str) -> str:
    """Return a basename safe for local downloads on Windows and Unix-like systems."""
    cleaned = _RESERVED_CHARS_RE.sub("-", str(value or "")).replace("..", "-")
    cleaned = _SPACE_RE.sub("-", cleaned.strip().strip("."))
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    if not cleaned:
        cleaned = "download"
    if cleaned.upper() in _RESERVED_WINDOWS_NAMES:
        cleaned = f"{cleaned}-file"
    return cleaned[:120].rstrip(".-") or "download"


def safe_download_filename(base: str, extension: str) -> str:
    """Build a safe filename with a controlled extension."""
    if not str(extension or "").strip().strip("."):
        raise ValueError("extension cannot be empty")
    safe_base = sanitize_filename(base)
    safe_extension = sanitize_filename(extension).lstrip(".").lower()
    return f"{safe_base}.{safe_extension}"
