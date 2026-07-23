from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.profile_models import AboutOutput, HeadlineOutput


def test_headline_character_count_correct():
    text = "Project Manager | Producto digital y métricas"
    headline = HeadlineOutput(text=text, character_count=len(text))

    assert headline.character_count == len(text)


def test_headline_character_count_incorrect_is_normalized():
    text = "Project Manager | Producto digital y métricas"

    headline = HeadlineOutput(text=text, character_count=len(text) + 1)

    assert headline.character_count == len(text)


def test_about_character_count_incorrect_is_normalized():
    text = "Soy Project Manager con experiencia en producto digital, métricas y coordinación de equipos. " * 4

    about = AboutOutput(text=text, character_count=len(text) + 7)

    assert about.character_count == len(text.strip())


def test_headline_more_than_220_characters_fails():
    text = "A" * 221

    with pytest.raises(ValidationError):
        HeadlineOutput(text=text, character_count=len(text))
