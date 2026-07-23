"""System font discovery for local image rendering."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from PIL import ImageFont

FONT_FALLBACK_WARNING = "No fue posible cargar una fuente adecuada. Se utilizará una fuente alternativa del sistema."

DEFAULT_FONT_NAMES = [
    "Segoe UI",
    "Arial",
    "Calibri",
    "Verdana",
    "DejaVu Sans",
    "Liberation Sans",
    "Noto Sans",
    "Helvetica",
]

_FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
_BOLD_MARKERS = ("bold", "bd", "black", "semibold", "demibold")
_DIRECT_FONT_FILES = {
    "segoeui": {
        False: ("segoeui.ttf", "SegoeUI.ttf"),
        True: ("segoeuib.ttf", "SegoeUIBold.ttf", "segoeuibold.ttf"),
    },
    "arial": {
        False: ("arial.ttf", "Arial.ttf"),
        True: ("arialbd.ttf", "Arial Bold.ttf", "Arial-Bold.ttf"),
    },
    "calibri": {
        False: ("calibri.ttf", "Calibri.ttf"),
        True: ("calibrib.ttf", "Calibri Bold.ttf", "Calibri-Bold.ttf"),
    },
    "verdana": {
        False: ("verdana.ttf", "Verdana.ttf"),
        True: ("verdanab.ttf", "Verdana Bold.ttf", "Verdana-Bold.ttf"),
    },
    "dejavusans": {
        False: ("DejaVuSans.ttf", "DejaVu Sans.ttf"),
        True: ("DejaVuSans-Bold.ttf", "DejaVu Sans Bold.ttf"),
    },
    "liberationsans": {
        False: ("LiberationSans-Regular.ttf", "Liberation Sans Regular.ttf"),
        True: ("LiberationSans-Bold.ttf", "Liberation Sans Bold.ttf"),
    },
    "notosans": {
        False: ("NotoSans-Regular.ttf", "Noto Sans Regular.ttf"),
        True: ("NotoSans-Bold.ttf", "Noto Sans Bold.ttf"),
    },
    "helvetica": {
        False: ("Helvetica.ttf", "Helvetica.ttc"),
        True: ("Helvetica-Bold.ttf", "HelveticaBold.ttf"),
    },
}


def find_font_path(preferred_names: list[str], bold: bool = False) -> str | None:
    """Return the first available system font path matching the preferred names."""
    directories = _candidate_font_dirs()
    for name in preferred_names:
        for filename in _filename_candidates(name, bold):
            for directory in directories:
                candidate = directory / filename
                if candidate.is_file():
                    return str(candidate)

    normalized_names = [_normalize_font_name(name) for name in preferred_names]
    for directory in directories:
        for font_file in _iter_font_files(directory):
            normalized_file = _normalize_font_name(font_file.stem)
            if not any(name in normalized_file for name in normalized_names):
                continue
            if bold and not _looks_bold(font_file.name):
                continue
            if not bold and _looks_bold(font_file.name):
                continue
            return str(font_file)
    return None


def load_font(
    preferred_names: list[str] | None,
    size: int,
    *,
    bold: bool = False,
) -> tuple[Any, str | None, list[str]]:
    """Load a TrueType font when available, otherwise return Pillow's fallback font."""
    names = preferred_names or DEFAULT_FONT_NAMES
    path = find_font_path(names, bold=bold)
    if path:
        try:
            return ImageFont.truetype(path, size=size), path, []
        except OSError:
            pass
    return _load_default_font(size), None, [FONT_FALLBACK_WARNING]


def font_supports_text(font: Any, text: str) -> bool:
    """Best-effort check that Pillow can measure and rasterize the requested text."""
    try:
        font.getbbox(text)
        font.getmask(text)
    except (OSError, UnicodeEncodeError, UnicodeError):
        return False
    return True


def _candidate_font_dirs() -> list[Path]:
    directories: list[Path] = []
    windir = os.environ.get("WINDIR")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if windir:
        directories.append(Path(windir) / "Fonts")
    if local_app_data:
        directories.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")

    home = Path.home()
    directories.extend(
        [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            home / ".fonts",
            home / ".local" / "share" / "fonts",
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            home / "Library" / "Fonts",
        ]
    )
    return _unique_existing_dirs(directories)


def _filename_candidates(name: str, bold: bool) -> tuple[str, ...]:
    normalized = _normalize_font_name(name)
    candidates = _DIRECT_FONT_FILES.get(normalized, {})
    return candidates.get(bold, ())


def _iter_font_files(directory: Path):
    try:
        yield from (path for path in directory.rglob("*") if path.suffix.lower() in _FONT_EXTENSIONS)
    except (OSError, PermissionError):
        return


def _normalize_font_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _looks_bold(filename: str) -> bool:
    normalized = _normalize_font_name(filename)
    return any(marker in normalized for marker in _BOLD_MARKERS)


def _load_default_font(size: int) -> Any:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _unique_existing_dirs(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    existing = []
    for path in paths:
        if path in seen or not path.exists() or not path.is_dir():
            continue
        seen.add(path)
        existing.append(path)
    return existing
