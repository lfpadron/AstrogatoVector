"""Deterministic audit for locally rendered LinkedIn banner PNGs."""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

from schemas.banner_models import (
    LINKEDIN_BANNER_FORMAT,
    LINKEDIN_BANNER_HEIGHT,
    LINKEDIN_BANNER_WIDTH,
    BannerAuditResult,
    BannerRenderResult,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ALLOWED_IMAGE_MODES = {"RGB", "RGBA"}


def audit_banner_result(result: BannerRenderResult) -> BannerAuditResult:
    """Audit render output without using AI or external resources."""
    findings: list[str] = []
    image_bytes = result.image_bytes
    file_signature_valid = bool(image_bytes and image_bytes.startswith(PNG_SIGNATURE))
    dimensions_valid = False
    mode_valid = False
    format_valid = False

    if not image_bytes:
        findings.append("El PNG no contiene bytes.")
    elif not file_signature_valid:
        findings.append("La firma PNG no es válida.")

    if image_bytes:
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                format_valid = image.format == LINKEDIN_BANNER_FORMAT
                dimensions_valid = image.size == (LINKEDIN_BANNER_WIDTH, LINKEDIN_BANNER_HEIGHT)
                mode_valid = image.mode in ALLOWED_IMAGE_MODES
        except (UnidentifiedImageError, OSError):
            findings.append("Pillow no pudo abrir o validar el PNG.")

    if not dimensions_valid:
        findings.append("Las dimensiones del banner no son 1584 x 396.")
    if image_bytes and not format_valid:
        findings.append("El formato del archivo no es PNG.")
    if image_bytes and not mode_valid:
        findings.append("El modo de imagen no es RGB ni RGBA.")
    if not result.contrast_passed:
        findings.append("El contraste no fue validado.")
    if not result.safe_zone_passed:
        findings.append("La zona segura no fue validada.")
    if not result.overflow_passed:
        findings.append("El texto no fue validado dentro del lienzo.")

    passed = (
        bool(image_bytes)
        and file_signature_valid
        and dimensions_valid
        and format_valid
        and mode_valid
        and result.contrast_passed
        and result.safe_zone_passed
        and result.overflow_passed
    )
    return BannerAuditResult(
        passed=passed,
        dimensions_valid=dimensions_valid,
        contrast_valid=result.contrast_passed,
        safe_zone_valid=result.safe_zone_passed,
        overflow_valid=result.overflow_passed,
        file_signature_valid=file_signature_valid,
        findings=_unique_preserving_order(findings),
    )


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
