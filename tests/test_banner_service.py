from __future__ import annotations

import io

import pytest
from PIL import Image

from schemas.banner_models import (
    DEFAULT_BANNER_FILENAME,
    LINKEDIN_BANNER_HEIGHT,
    LINKEDIN_BANNER_WIDTH,
    BannerRenderInput,
)
from schemas.enums import OutputLanguage
from services.banner_service import (
    BANNER_TEMPLATES,
    BannerService,
    TEXT_TOO_LONG_MESSAGE,
    build_banner_render_fingerprint,
    validate_safe_zone,
)


def test_render_banner_generates_valid_png_for_each_template():
    service = BannerService()

    for template_id in BANNER_TEMPLATES:
        result = service.render_banner(_render_input(template_id=template_id))

        assert result.success is True
        assert result.image_bytes is not None
        assert result.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        assert result.filename == DEFAULT_BANNER_FILENAME
        assert result.width == LINKEDIN_BANNER_WIDTH
        assert result.height == LINKEDIN_BANNER_HEIGHT
        assert result.contrast_passed is True
        assert result.safe_zone_passed is True
        assert result.overflow_passed is True
        assert validate_safe_zone(result.text_bounding_boxes) is True

        with Image.open(io.BytesIO(result.image_bytes)) as image:
            assert image.format == "PNG"
            assert image.size == (LINKEDIN_BANNER_WIDTH, LINKEDIN_BANNER_HEIGHT)
            assert image.mode in {"RGB", "RGBA"}


def test_render_result_does_not_serialize_png_bytes():
    result = BannerService().render_banner(_render_input())

    dumped = result.model_dump()

    assert result.image_bytes
    assert "image_bytes" not in dumped


def test_invalid_template_is_rejected():
    payload = _render_input().model_dump()
    payload["template_id"] = "flashy_template"

    result = BannerService().render_banner(payload)

    assert result.success is False
    assert "La plantilla seleccionada no es válida." in result.errors
    assert result.image_bytes is None


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("supporting_line", "Contacto demo@example.com", "correo"),
        ("supporting_line", "Telefono 55 1234 5678", "teléfono"),
        ("supporting_line", "RFC ABC010203AB1", "RFC"),
        ("supporting_line", "CURP GODE561231HDFRRN09", "CURP"),
    ],
)
def test_sensitive_banner_content_is_rejected(field: str, value: str, expected_error: str):
    payload = _render_input().model_dump()
    payload[field] = value

    result = BannerService().render_banner(payload)

    assert result.success is False
    assert any(expected_error.casefold() in error.casefold() for error in result.errors)
    assert result.image_bytes is None


def test_urls_warn_without_blocking_render():
    payload = _render_input().model_dump()
    payload["supporting_line"] = "Portafolio en www.example.com"

    result = BannerService().render_banner(payload)

    assert result.success is True
    assert any("URL" in warning or "URLs" in warning for warning in result.warnings)


def test_impossible_text_is_rejected_without_truncation():
    payload = _render_input().model_dump()
    payload["primary_line"] = "X" * 120
    payload["specialty_line"] = "Y" * 200

    result = BannerService().render_banner(payload)

    assert result.success is False
    assert TEXT_TOO_LONG_MESSAGE in result.errors
    assert result.image_bytes is None


def test_banner_fingerprint_changes_with_text_and_template():
    base = _render_input()
    changed_text = base.model_copy(update={"primary_line": "Project Manager de tecnologia"})
    changed_template = base.model_copy(update={"template_id": "professional_dark"})

    assert build_banner_render_fingerprint(base) != build_banner_render_fingerprint(changed_text)
    assert build_banner_render_fingerprint(base) != build_banner_render_fingerprint(changed_template)


def _render_input(template_id: str = "professional_light") -> BannerRenderInput:
    return BannerRenderInput(
        primary_line="Liderazgo de Proyectos y Transformacion Digital",
        specialty_line="Project Management · Gestion de Riesgos · Inteligencia Artificial",
        supporting_line="Tecnologia · Negocio · Equipos multidisciplinarios",
        visual_concept="Geometria vectorial minima con nodos discretos.",
        template_id=template_id,
        output_language=OutputLanguage.ES,
    )
