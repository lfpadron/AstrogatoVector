from __future__ import annotations

import io

from PIL import Image

from schemas.banner_models import BannerRenderInput, BannerRenderResult
from schemas.enums import OutputLanguage
from services.banner_audit_service import audit_banner_result
from services.banner_service import BannerService


def test_banner_audit_accepts_valid_rendered_png():
    result = BannerService().render_banner(_render_input())

    audit = audit_banner_result(result)

    assert audit.passed is True
    assert audit.file_signature_valid is True
    assert audit.dimensions_valid is True
    assert audit.contrast_valid is True
    assert audit.safe_zone_valid is True
    assert audit.overflow_valid is True
    assert audit.findings == []


def test_banner_audit_rejects_invalid_bytes():
    result = BannerRenderResult(
        success=True,
        image_bytes=b"not-a-png",
        contrast_passed=True,
        safe_zone_passed=True,
        overflow_passed=True,
    )

    audit = audit_banner_result(result)

    assert audit.passed is False
    assert audit.file_signature_valid is False
    assert audit.dimensions_valid is False
    assert audit.findings


def test_banner_audit_rejects_wrong_dimensions():
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "#ffffff").save(buffer, format="PNG")
    result = BannerRenderResult(
        success=True,
        image_bytes=buffer.getvalue(),
        contrast_passed=True,
        safe_zone_passed=True,
        overflow_passed=True,
    )

    audit = audit_banner_result(result)

    assert audit.passed is False
    assert audit.file_signature_valid is True
    assert audit.dimensions_valid is False


def test_banner_audit_rejects_failed_render_flags_even_with_valid_png():
    result = BannerService().render_banner(_render_input()).model_copy(update={"contrast_passed": False})

    audit = audit_banner_result(result)

    assert audit.passed is False
    assert audit.contrast_valid is False


def _render_input() -> BannerRenderInput:
    return BannerRenderInput(
        primary_line="Project Manager",
        specialty_line="Agile · Jira · Stakeholders",
        supporting_line="Tecnologia y negocio",
        template_id="professional_light",
        output_language=OutputLanguage.ES,
    )
