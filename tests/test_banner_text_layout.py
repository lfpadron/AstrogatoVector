from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.banner_models import (
    BANNER_TEXT_START_X,
    LINKEDIN_BANNER_WIDTH,
    MAX_BANNER_PRIMARY_CHARS,
    BannerRenderInput,
)
from schemas.enums import OutputLanguage
from services.banner_service import BannerService, find_best_font_size, wrap_text_to_width


@pytest.mark.parametrize(
    ("primary", "specialty", "supporting"),
    [
        ("Project Manager", "Agile | Jira | Stakeholders", None),
        ("Gerencia de Tecnología con foco en transformación digital", "C++ · C# · .NET · Data & AI", "Español · Inglés · equipos multidisciplinarios"),
        ("Línea uno\nLínea dos", "Agile · Jira\nStakeholder management", "Apoyo ejecutivo"),
        ("Transformación Digital", "Datos • IA • Automatización", ""),
    ],
)
def test_layout_supports_common_professional_characters(primary: str, specialty: str, supporting: str | None):
    result = BannerService().render_banner(
        BannerRenderInput(
            primary_line=primary,
            specialty_line=specialty,
            supporting_line=supporting,
            visual_concept="network nodes minimal",
            template_id="technology_clean",
            output_language=OutputLanguage.ES,
        )
    )

    assert result.success is True
    assert result.primary_line_count in {1, 2}
    assert result.specialty_line_count in {1, 2}
    assert result.supporting_line_count in {0, 1, 2}
    assert result.overflow_passed is True
    assert result.safe_zone_passed is True


def test_text_normalization_collapses_spaces_and_keeps_allowed_breaks():
    render_input = BannerRenderInput(
        primary_line="  Project    Manager  ",
        specialty_line=" Agile   ·   Jira \n Stakeholders ",
        supporting_line=" Tecnologia    y    negocio ",
        template_id="professional_light",
        output_language=OutputLanguage.ES,
    )

    assert render_input.primary_line == "Project Manager"
    assert render_input.specialty_line == "Agile · Jira\nStakeholders"
    assert render_input.supporting_line == "Tecnologia y negocio"


def test_too_many_manual_breaks_are_rejected():
    with pytest.raises(ValidationError):
        BannerRenderInput(
            primary_line="Uno\nDos\nTres\nCuatro",
            specialty_line="Agile",
            template_id="professional_light",
            output_language=OutputLanguage.ES,
        )


def test_recommended_length_warning_does_not_block_render():
    result = BannerService().render_banner(
        BannerRenderInput(
            primary_line="Liderazgo de programas tecnológicos complejos con transformación digital ejecutiva",
            specialty_line="Project Management · Riesgos · IA · Operación · Gobierno · Stakeholders · Mejora continua",
            supporting_line="Tecnología · Negocio · Equipos multidisciplinarios",
            template_id="executive_blue",
            output_language=OutputLanguage.ES,
        )
    )

    assert result.success is True
    assert result.warnings
    assert result.primary_font_size is not None


def test_single_unbreakable_word_fails_instead_of_truncating():
    result = BannerService().render_banner(
        {
            "primary_line": "X" * MAX_BANNER_PRIMARY_CHARS,
            "specialty_line": "Agile",
            "template_id": "professional_dark",
            "output_language": "es",
        }
    )

    assert result.success is False
    assert result.image_bytes is None


def test_find_best_font_size_and_wrap_respect_canvas_width():
    max_width = LINKEDIN_BANNER_WIDTH - BANNER_TEXT_START_X - 70
    fit = find_best_font_size(
        "Project Management · Inteligencia Artificial · Transformación Digital",
        max_width,
        max_lines=2,
        initial_size=48,
        minimum_size=30,
        bold=True,
    )

    assert fit is not None
    size, lines = fit
    assert 30 <= size <= 48
    assert len(lines) <= 2


def test_wrap_rejects_separator_at_line_edges():
    tiny_width = 1
    assert wrap_text_to_width("Agile · Jira", _TinyFont(), tiny_width, max_lines=2) is None


class _TinyFont:
    def getbbox(self, text, *args, **kwargs):
        return (0, 0, len(text) * 10, 10)
