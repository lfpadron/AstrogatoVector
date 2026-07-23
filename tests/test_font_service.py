from __future__ import annotations

from PIL import ImageFont

from services import font_service
from services.font_service import FONT_FALLBACK_WARNING, find_font_path, font_supports_text, load_font


def test_find_font_path_returns_none_for_missing_font(monkeypatch):
    monkeypatch.setattr(font_service, "_candidate_font_dirs", lambda: [])

    assert find_font_path(["Definitely Missing Font"]) is None


def test_find_font_path_uses_common_filename_candidates(tmp_path, monkeypatch):
    font_file = tmp_path / "arial.ttf"
    font_file.write_bytes(b"not-a-real-font-but-discovery-only")
    monkeypatch.setattr(font_service, "_candidate_font_dirs", lambda: [tmp_path])

    assert find_font_path(["Arial"]) == str(font_file)


def test_load_font_falls_back_without_failing(monkeypatch):
    monkeypatch.setattr(font_service, "find_font_path", lambda preferred_names, bold=False: None)

    font, path, warnings = load_font(["Missing"], 24)

    assert font is not None
    assert path is None
    assert warnings == [FONT_FALLBACK_WARNING]


def test_font_support_check_accepts_basic_text():
    font = ImageFont.load_default()

    assert font_supports_text(font, "Project Manager C++ C# .NET") is True
