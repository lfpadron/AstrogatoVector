"""Deterministic validation for the final deliverable package."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from pydantic import TypeAdapter

from schemas.deliverable_models import FinalDeliverablePackage

SENSITIVE_CONTENT_MESSAGE = (
    "Se detectó un posible dato sensible en el contenido editable. Revísalo antes de generar el paquete."
)

_PLACEHOLDER_PATTERNS = (
    re.compile(r"\[(?:TBD|TODO|PLACEHOLDER)\]", re.IGNORECASE),
    re.compile(r"\blorem ipsum\b", re.IGNORECASE),
    re.compile(r"\binsert text\b", re.IGNORECASE),
    re.compile(r"\bpendiente de completar\b", re.IGNORECASE),
)
_FORBIDDEN_TERMS = (
    "OPENAI_API_KEY",
    "api_key",
    "secret key",
    "raw_openai_response",
    "respuesta cruda",
    "system prompt",
    "developer prompt",
    "prompt:",
)
_SENSITIVE_PATTERNS = (
    ("RFC", re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)),
    (
        "CURP",
        re.compile(r"\b[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE),
    ),
    ("tarjeta", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("cuenta bancaria", re.compile(r"\b\d{18}\b")),
    ("contraseña", re.compile(r"\b(?:password|contrase(?:n|ñ)a|pwd)\s*[:=]", re.IGNORECASE)),
    ("identificación oficial", re.compile(r"\b(?:INE|IFE|passport|pasaporte)\s*[:#]?\s*[A-Z0-9-]{6,}\b", re.IGNORECASE)),
)


def validate_final_package(package: FinalDeliverablePackage | None) -> tuple[bool, list[str], list[str]]:
    """Return blocking findings and non-blocking warnings for a package."""
    findings: list[str] = []
    warnings: list[str] = []
    if package is None:
        return False, ["error: auditoría presente: el paquete final no existe."], warnings

    _validate_required_content(package, findings)
    _validate_scores(package, findings)
    _validate_supported_content(package, findings)
    _validate_text_safety(package, findings, warnings)
    _validate_serializable(package, findings)
    if not package.banner_included:
        warnings.append("Banner PNG not included.")
    return not findings, findings, warnings


def _validate_required_content(package: FinalDeliverablePackage, findings: list[str]) -> None:
    if not package.headline.strip():
        findings.append("error: headline no vacío.")
    if len(package.headline) > 220:
        findings.append("error: headline no supera 220 caracteres.")
    if not package.about.strip():
        findings.append("error: About no vacío.")
    if not package.experiences:
        findings.append("error: experiencias presentes.")
    if not package.prioritized_skills:
        findings.append("error: skills presentes.")
    if not package.ats_keywords:
        findings.append("error: keywords presentes.")
    if package.compatibility_report is None:
        findings.append("error: compatibilidad presente.")
    if package.audit_report is None or not package.audit_report.success:
        findings.append("error: auditoría presente.")
    if not package.banner_primary_line.strip() or not package.banner_specialty_line.strip():
        findings.append("error: banner textual válido.")


def _validate_scores(package: FinalDeliverablePackage, findings: list[str]) -> None:
    values = [package.compatibility_report.average_compatibility_score]
    if package.audit_report is None:
        return
    if package.audit_report.overall_score is not None:
        values.append(package.audit_report.overall_score)
    if package.audit_report.linkedin_positioning is not None:
        values.append(package.audit_report.linkedin_positioning.score)
    if package.audit_report.ats_estimation is not None:
        values.append(package.audit_report.ats_estimation.score)
    values.extend(job.compatibility_score for job in package.compatibility_report.job_compatibilities)
    if any(value < 0 or value > 100 for value in values):
        findings.append("error: scores entre 0 y 100.")


def _validate_supported_content(package: FinalDeliverablePackage, findings: list[str]) -> None:
    unsupported = [
        f"{experience.employer} - {experience.suggested_role_title}"
        for experience in package.experiences
        if experience.unsupported_claims
    ]
    if unsupported:
        findings.append("error: no hay unsupported_claims en experiencias exportables.")


def _validate_text_safety(
    package: FinalDeliverablePackage,
    findings: list[str],
    warnings: list[str],
) -> None:
    for path, value in _iter_text_fields(package.model_dump(mode="json")):
        normalized = value.strip()
        if not normalized:
            continue
        for pattern in _PLACEHOLDER_PATTERNS:
            if pattern.search(normalized):
                findings.append(f"error: no hay placeholders en {path}.")
                break
        for term in _FORBIDDEN_TERMS:
            if term.casefold() in normalized.casefold():
                findings.append(f"error: no se exportan secretos, prompts ni respuestas crudas en {path}.")
                break
        for label, pattern in _SENSITIVE_PATTERNS:
            if pattern.search(normalized):
                findings.append(f"error: posible dato sensible ({label}) en {path}. {SENSITIVE_CONTENT_MESSAGE}")
                break
    if package.audit_report is not None and package.audit_report.warnings:
        warnings.extend(f"Auditoría: {warning}" for warning in package.audit_report.warnings)


def _validate_serializable(package: FinalDeliverablePackage, findings: list[str]) -> None:
    try:
        json.dumps(package.model_dump(mode="json"), ensure_ascii=False)
        TypeAdapter(FinalDeliverablePackage).validate_python(package.model_dump(mode="json"))
    except (TypeError, ValueError) as exc:
        findings.append(f"error: no hay objetos no serializables: {exc}")


def _iter_text_fields(value: Any, prefix: str = "package") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix, value
        return
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_text_fields(child, f"{prefix}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_text_fields(child, f"{prefix}[{index}]")
