from __future__ import annotations

import pytest

from utils.filename_utils import safe_download_filename, sanitize_filename


def test_sanitize_filename_removes_paths_reserved_chars_and_dotdot():
    assert sanitize_filename("../mi:archivo\\final?.pdf") == "mi-archivo-final-.pdf"
    assert "/" not in sanitize_filename("a/b")
    assert "\\" not in sanitize_filename("a\\b")
    assert ".." not in sanitize_filename("a..b")


def test_safe_download_filename_controls_extension():
    assert safe_download_filename("perfil profesional", ".PDF") == "perfil-profesional.pdf"
    with pytest.raises(ValueError):
        safe_download_filename("perfil", "")
