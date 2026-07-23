"""Deterministic evidence checks for extracted candidate profiles."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from schemas.enums import EvidenceStatus
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.extraction_models import EvidenceAuditFinding, EvidenceAuditResult
from utils.constants import MAX_REASONABLE_YEARS_EXPERIENCE

SOURCE_SECTION_HINTS = {
    "cv",
    "linkedin",
    "perfil",
    "profile",
    "experiencia",
    "experience",
    "educacion",
    "education",
    "certificacion",
    "certification",
    "idioma",
    "language",
    "skill",
    "habilidad",
    "fuente",
    "source",
    "resumen",
    "summary",
}

FIGURE_PATTERN = re.compile(
    r"(?<![\w])(?:[$€£]\s*)?\d+(?:[.,]\d+)?(?:\s?%|\s?(?:k|m|mil|millones|millions))?(?![\w])",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


def audit_candidate_profile_evidence(
    profile: CandidateProfessionalProfile,
    source_text: str,
) -> EvidenceAuditResult:
    """Audit evidence references and obvious unsupported claims."""
    findings: list[EvidenceAuditFinding] = []
    normalized_source = _normalize_for_match(source_text)

    _audit_total_years(profile, source_text, findings)
    _audit_skills(profile.skills, "skills", normalized_source, findings)
    _audit_evidence_items(profile.leadership_capabilities, "leadership_capabilities", normalized_source, findings)
    _audit_evidence_items(profile.education, "education", normalized_source, findings)
    _audit_evidence_items(profile.certifications, "certifications", normalized_source, findings)
    _audit_evidence_items(profile.languages, "languages", normalized_source, findings)
    _audit_achievements(profile.achievements, "achievements", normalized_source, findings)
    _audit_employment_history(profile.employment_history, normalized_source, findings)

    passed = not any(finding.severity == "error" for finding in findings)
    return EvidenceAuditResult(passed=passed, findings=findings)


def _audit_total_years(
    profile: CandidateProfessionalProfile,
    source_text: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    total = profile.total_years_experience
    if total is None:
        return
    if total < 0:
        _add_error(findings, "total_years_experience", "El total de experiencia no puede ser negativo.")
    if total > MAX_REASONABLE_YEARS_EXPERIENCE:
        _add_error(findings, "total_years_experience", "El total de experiencia excede un rango razonable.")
    if len(set(YEAR_PATTERN.findall(source_text))) < 2:
        _add_warning(
            findings,
            "total_years_experience",
            "El total de experiencia fue informado aunque las fuentes no tienen fechas suficientes.",
        )


def _audit_employment_history(
    employment_history: list[EmploymentEntry],
    normalized_source: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    seen_jobs: set[str] = set()
    for index, employment in enumerate(employment_history):
        path = f"employment_history[{index}]"
        key = _normalize_key(
            "|".join(
                [
                    employment.employer,
                    employment.role_title,
                    employment.start_date or "",
                    employment.end_date or "",
                ]
            )
        )
        if key in seen_jobs:
            _add_error(findings, path, "Se detectó un empleo duplicado evidente.")
        seen_jobs.add(key)
        _audit_evidence_items(employment.responsibilities, f"{path}.responsibilities", normalized_source, findings)
        _audit_achievements(employment.achievements, f"{path}.achievements", normalized_source, findings)
        _audit_skills(employment.technologies, f"{path}.technologies", normalized_source, findings)


def _audit_skills(
    skills: list[CandidateSkill],
    path: str,
    normalized_source: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    seen_skills: set[str] = set()
    for index, skill in enumerate(skills):
        item_path = f"{path}[{index}]"
        normalized_name = _normalize_key(skill.normalized_name)
        if normalized_name in seen_skills:
            _add_error(findings, item_path, "Se detectó una habilidad duplicada por nombre normalizado.")
        seen_skills.add(normalized_name)
        if _status_value(skill.evidence_status) == EvidenceStatus.MISSING.value and skill.years_experience is not None:
            _add_error(findings, item_path, "Una habilidad MISSING no debe incluir years_experience.")
        _audit_confidence(skill.evidence_status, skill.confidence, item_path, findings)
        _audit_references(skill.evidence_status, skill.references, item_path, normalized_source, findings)


def _audit_evidence_items(
    items: list[EvidenceItem],
    path: str,
    normalized_source: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        _audit_confidence(item.status, item.confidence, item_path, findings)
        if _status_value(item.status) == EvidenceStatus.CONFLICT.value and not item.notes:
            _add_error(findings, item_path, "Una afirmación CONFLICT debe incluir explicación.")
        _audit_references(item.status, item.references, item_path, normalized_source, findings)


def _audit_achievements(
    achievements: list[Achievement],
    path: str,
    normalized_source: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    for index, achievement in enumerate(achievements):
        item_path = f"{path}[{index}]"
        _audit_references(achievement.evidence_status, achievement.references, item_path, normalized_source, findings)
        _audit_figures(achievement, item_path, normalized_source, findings)


def _audit_references(
    status: EvidenceStatus | str,
    references: list[EvidenceReference],
    path: str,
    normalized_source: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    status_value = _status_value(status)
    if status_value == EvidenceStatus.SUPPORTED.value and not references:
        _add_error(findings, path, "Toda afirmación SUPPORTED debe incluir referencias.")

    for index, reference in enumerate(references):
        ref_path = f"{path}.references[{index}]"
        if not reference.source_section.strip():
            _add_error(findings, ref_path, "La sección fuente no puede estar vacía.")
        if not reference.source_excerpt.strip():
            _add_error(findings, ref_path, "El fragmento de evidencia no puede estar vacío.")
        if len(reference.source_excerpt) > 500:
            _add_error(findings, ref_path, "El fragmento de evidencia excede 500 caracteres.")
        if not _source_section_has_hint(reference.source_section):
            _add_warning(findings, ref_path, "La sección fuente no parece identificar una sección conocida.")

        if status_value == EvidenceStatus.SUPPORTED.value and not _excerpt_found(
            reference.source_excerpt,
            normalized_source,
        ):
            _add_error(
                findings,
                ref_path,
                "La referencia declarada como evidencia no pudo localizarse en las fuentes.",
            )


def _audit_confidence(
    status: EvidenceStatus | str,
    confidence: float,
    path: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    status_value = _status_value(status)
    if status_value == EvidenceStatus.SUPPORTED.value:
        if confidence < 0.50:
            _add_error(findings, path, "SUPPORTED no debe tener confidence menor a 0.50.")
        elif confidence < 0.70:
            _add_warning(findings, path, "SUPPORTED con confidence menor a 0.70 requiere revisión humana.")
    if status_value == EvidenceStatus.INFERRED.value and confidence > 0.95:
        _add_warning(findings, path, "INFERRED con confidence muy alto debe revisarse.")


def _audit_figures(
    achievement: Achievement,
    path: str,
    normalized_source: str,
    findings: list[EvidenceAuditFinding],
) -> None:
    checked_text = " ".join(
        part
        for part in [achievement.description, achievement.measurable_result]
        if part
    )
    for figure in _extract_figures(checked_text):
        if not _figure_found(figure, normalized_source):
            _add_error(findings, path, f"La cifra '{figure}' no se encontró en las fuentes.")


def _extract_figures(text: str) -> list[str]:
    return [match.group(0).strip() for match in FIGURE_PATTERN.finditer(text)]


def _figure_found(figure: str, normalized_source: str) -> bool:
    normalized_figure = _normalize_for_match(figure)
    compact_figure = re.sub(r"\D", "", figure)
    if normalized_figure and normalized_figure in normalized_source:
        return True
    if compact_figure and compact_figure in re.sub(r"\D", "", normalized_source):
        return True
    try:
        decimal = Decimal(figure.replace("%", "").replace("$", "").replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return False
    return str(decimal.normalize()) in normalized_source


def _excerpt_found(excerpt: str, normalized_source: str) -> bool:
    normalized_excerpt = _normalize_for_match(excerpt)
    return bool(normalized_excerpt) and normalized_excerpt in normalized_source


def _source_section_has_hint(source_section: str) -> bool:
    normalized = _normalize_for_match(source_section)
    return any(hint in normalized for hint in SOURCE_SECTION_HINTS)


def _status_value(status: EvidenceStatus | str) -> str:
    return status.value if isinstance(status, EvidenceStatus) else str(status)


def _normalize_key(value: str) -> str:
    return _normalize_for_match(value)


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    ascii_text = ascii_text.casefold()
    ascii_text = re.sub(r"[^\w%$€£]+", " ", ascii_text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _add_error(findings: list[EvidenceAuditFinding], path: str, message: str) -> None:
    findings.append(EvidenceAuditFinding(severity="error", path=path, message=message))


def _add_warning(findings: list[EvidenceAuditFinding], path: str, message: str) -> None:
    findings.append(EvidenceAuditFinding(severity="warning", path=path, message=message))
