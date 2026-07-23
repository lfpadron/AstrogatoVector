"""Local evidence audit for targeted CV output."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from typing import Iterable

from schemas.compatibility_models import JobCompatibility
from schemas.enums import EvidenceStatus, RequirementCoverage
from schemas.evidence_models import CandidateProfessionalProfile, EmploymentEntry, EvidenceItem
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import (
    TargetedCV,
    TargetedCVAuditFinding,
    TargetedCVAuditResult,
    TargetedCVExperienceEntry,
)

_FORBIDDEN_EXPORT_MARKERS = (
    "compatibility_score",
    "request_id",
    "input_tokens",
    "output_tokens",
    "prompt",
    "raw_response",
    "openai",
)
_PLACEHOLDER_PATTERNS = (
    "lorem ipsum",
    "por completar",
    "pendiente",
    "xxx",
    "tbd",
    "[",
    "]",
    "{",
    "}",
)
_SENSITIVE_PATTERNS = (
    r"\bRFC\b",
    r"\bCURP\b",
    r"\bcontrase(?:n|ñ)a\b",
    r"\bcuenta bancaria\b",
    r"\bdomicilio particular\b",
)
_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s?%?|\b\d{4}\b")
_SENIORITY_RANK = {
    "entry": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "manager": 5,
    "director": 6,
    "executive": 7,
    "unspecified": 0,
}


def audit_targeted_cv(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
) -> TargetedCVAuditResult:
    """Validate that the targeted CV stays inside supported evidence and job context."""
    findings: list[TargetedCVAuditFinding] = []
    _audit_target_identity(targeted_cv, job_analysis, job_compatibility, findings)
    _audit_header(targeted_cv, candidate_profile, findings)
    _audit_summary(targeted_cv, candidate_profile, findings)
    _audit_experience(targeted_cv, candidate_profile, findings)
    _audit_skills(targeted_cv, candidate_profile, findings)
    _audit_keywords(targeted_cv, candidate_profile, job_analysis, job_compatibility, findings)
    _audit_optional_sections(targeted_cv, findings)
    _audit_forbidden_markers(targeted_cv, findings)
    return TargetedCVAuditResult(passed=not _has_errors(findings), findings=findings)


def _audit_target_identity(
    targeted_cv: TargetedCV,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    findings: list[TargetedCVAuditFinding],
) -> None:
    if targeted_cv.target_job_index != job_analysis.job_index or targeted_cv.target_job_index != job_compatibility.job_index:
        _error(findings, "target_job_index", "El índice de vacante no coincide con el análisis y compatibilidad.")
    if _norm(targeted_cv.target_job_title) != _norm(job_analysis.title):
        _error(findings, "target_job_title", "El título objetivo no coincide con JobAnalysis.")
    if _norm(targeted_cv.header.target_role_title) != _norm(job_analysis.title):
        _error(findings, "header.target_role_title", "El título del encabezado no coincide con la vacante objetivo.")
    if _norm(targeted_cv.target_company or "") != _norm(job_analysis.company or ""):
        _error(findings, "target_company", "La empresa objetivo no coincide con JobAnalysis.")
    if _norm(job_compatibility.job_title) != _norm(job_analysis.title):
        _error(findings, "job_compatibility.job_title", "La compatibilidad usada no corresponde al análisis de vacante.")


def _audit_header(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    findings: list[TargetedCVAuditFinding],
) -> None:
    if not targeted_cv.header.candidate_name:
        _warning(findings, "header.candidate_name", "El perfil profesional no contiene nombre explícito para el encabezado.")
    if not any([targeted_cv.header.email, targeted_cv.header.phone, targeted_cv.header.linkedin_url]):
        _warning(findings, "header.contact", "No se agregó contacto porque no existe información explícita disponible.")
    if _title_inflates_seniority(targeted_cv.header.professional_title, candidate_profile):
        _error(findings, "header.professional_title", "El título profesional parece inflar el seniority respaldado.")


def _audit_summary(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    findings: list[TargetedCVAuditFinding],
) -> None:
    text = targeted_cv.summary.text.strip()
    if len(text) < 220:
        _warning(findings, "summary.text", "El resumen es corto para un CV profesional específico por vacante.")
    if len(text) > 900:
        _error(findings, "summary.text", "El resumen es demasiado largo para un CV ATS-friendly.")
    if not targeted_cv.summary.evidence_items and not targeted_cv.summary.claims_requiring_review:
        _error(findings, "summary.evidence_items", "El resumen requiere evidencia o claims marcados para revisión.")
    _audit_numbers(text, candidate_profile, "summary.text", findings)


def _audit_experience(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    findings: list[TargetedCVAuditFinding],
) -> None:
    source_entries = candidate_profile.employment_history
    cv_entries = targeted_cv.experience
    if len(cv_entries) != len(source_entries):
        _error(findings, "experience", "Cada empleo fuente debe aparecer exactamente una vez en el CV objetivo.")

    source_keys = [_employment_key(item) for item in source_entries]
    cv_keys = [_cv_employment_key(item) for item in cv_entries]
    for index, source_key in enumerate(source_keys):
        if index >= len(cv_keys) or cv_keys[index] != source_key:
            _error(findings, f"experience[{index}]", "El empleo no conserva empleador, cargo fuente, fechas, ubicación u orden.")
    counts = Counter(cv_keys)
    for key, count in counts.items():
        if count > 1:
            _error(findings, "experience", f"El empleo {key[0]} aparece duplicado.")

    for index, entry in enumerate(cv_entries):
        source = source_entries[index] if index < len(source_entries) else None
        if _title_inflates_seniority(entry.display_role_title, candidate_profile, source):
            _error(findings, f"experience[{index}].display_role_title", "El cargo mostrado parece inflar el seniority respaldado.")
        if not entry.included:
            if source and source.is_current:
                _warning(findings, f"experience[{index}].included", "Se excluyó un empleo actual; revisa si conviene mostrarlo.")
            continue
        if not 1 <= len(entry.bullets) <= 6:
            _error(findings, f"experience[{index}].bullets", "Cada empleo incluido debe tener entre 1 y 6 bullets.")
        source_text = _source_employment_text(source) if source else ""
        for bullet_index, bullet in enumerate(entry.bullets):
            path = f"experience[{index}].bullets[{bullet_index}]"
            if not bullet.evidence_items and not bullet.claims_requiring_review:
                _error(findings, path, "Cada bullet requiere evidencia o claims marcados para revisión.")
            _audit_numbers(bullet.text, candidate_profile, f"{path}.text", findings)
            for keyword in bullet.included_keywords:
                if _norm(keyword) and _norm(keyword) not in _norm(source_text + " " + _profile_supported_text(candidate_profile)):
                    _warning(findings, f"{path}.included_keywords", "Una keyword del bullet no aparece claramente en la evidencia fuente.")
        for technology in entry.technologies:
            if _norm(technology) and source and _norm(technology) not in _norm(source_text):
                _error(findings, f"experience[{index}].technologies", "La tecnología no aparece respaldada en el empleo fuente.")
        for industry in entry.industries:
            if _norm(industry) and source and _norm(industry) not in {_norm(value) for value in source.industries}:
                _error(findings, f"experience[{index}].industries", "La industria no corresponde al empleo fuente.")


def _audit_skills(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    findings: list[TargetedCVAuditFinding],
) -> None:
    if len(targeted_cv.skills) > 18:
        _error(findings, "skills", "El CV objetivo no debe priorizar más de 18 skills.")
    priorities = sorted(skill.priority for skill in targeted_cv.skills)
    if priorities and priorities != list(range(1, len(priorities) + 1)):
        _error(findings, "skills.priority", "Las prioridades de skills deben ser consecutivas desde 1.")
    names = [_norm(skill.name) for skill in targeted_cv.skills]
    for name, count in Counter(names).items():
        if name and count > 1:
            _error(findings, "skills", f"Skill duplicada: {name}.")

    supported_skill_names = {_norm(skill.name) for skill in candidate_profile.skills if _is_supported(skill.evidence_status)}
    supported_skill_names.update(
        _norm(skill.normalized_name) for skill in candidate_profile.skills if _is_supported(skill.evidence_status)
    )
    for index, skill in enumerate(targeted_cv.skills):
        if not _is_supported(skill.evidence_status):
            _error(findings, f"skills[{index}].evidence_status", "No se pueden presentar skills MISSING o CONFLICT como capacidades.")
        if _norm(skill.name) not in supported_skill_names:
            _error(findings, f"skills[{index}].name", "La skill no aparece como capacidad respaldada del candidato.")
        if not skill.source_evidence and not skill.claims_requiring_review:
            _error(findings, f"skills[{index}].source_evidence", "La skill requiere evidencia o claims para revisión.")


def _audit_keywords(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    findings: list[TargetedCVAuditFinding],
) -> None:
    job_terms = {_norm(term) for term in _job_terms(job_analysis)}
    supported_terms = {_norm(term) for term in _supported_terms(candidate_profile, job_compatibility)}
    for keyword in targeted_cv.ats_keywords_used:
        normalized = _norm(keyword)
        if normalized and normalized not in job_terms:
            _warning(findings, "ats_keywords_used", "La keyword usada no aparece en la vacante objetivo estructurada.")
        if normalized and normalized not in supported_terms:
            _error(findings, "ats_keywords_used", "La keyword usada no está respaldada por el perfil o compatibilidad.")
    for keyword in targeted_cv.ats_keywords_missing:
        normalized = _norm(keyword)
        if normalized and normalized in {_norm(value) for value in targeted_cv.ats_keywords_used}:
            _error(findings, "ats_keywords_missing", "Una keyword no puede estar usada y faltante al mismo tiempo.")
    for keyword in targeted_cv.ats_keywords_omitted:
        if _norm(keyword) in {_norm(value) for value in targeted_cv.ats_keywords_used}:
            _error(findings, "ats_keywords_omitted", "Una keyword omitida no puede aparecer como usada.")


def _audit_optional_sections(targeted_cv: TargetedCV, findings: list[TargetedCVAuditFinding]) -> None:
    for section_name in ("education", "certifications", "languages"):
        entries = getattr(targeted_cv, section_name)
        for index, entry in enumerate(entries):
            if entry.visible and not entry.evidence_items and not entry.claims_requiring_review:
                _error(findings, f"{section_name}[{index}]", "El elemento visible requiere evidencia o claim marcado para revisión.")


def _audit_forbidden_markers(targeted_cv: TargetedCV, findings: list[TargetedCVAuditFinding]) -> None:
    text = _exportable_text(targeted_cv).casefold()
    for marker in _FORBIDDEN_EXPORT_MARKERS:
        if marker.casefold() in text:
            _error(findings, "targeted_cv", f"El CV contiene marcador interno no permitido: {marker}.")
    for marker in _PLACEHOLDER_PATTERNS:
        if marker in text:
            _warning(findings, "targeted_cv", f"El CV parece contener placeholder o texto incompleto: {marker}.")
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            _error(findings, "targeted_cv", "El CV contiene información sensible no permitida.")


def _exportable_text(targeted_cv: TargetedCV) -> str:
    values: list[str] = [
        targeted_cv.header.candidate_name or "",
        targeted_cv.header.professional_title,
        targeted_cv.header.target_role_title,
        targeted_cv.header.email or "",
        targeted_cv.header.phone or "",
        targeted_cv.header.linkedin_url or "",
        targeted_cv.header.location or "",
        targeted_cv.summary.text,
    ]
    values.extend(skill.name for skill in targeted_cv.skills)
    for entry in targeted_cv.experience:
        values.extend([entry.source_role_title, entry.display_role_title, entry.employer, entry.location or ""])
        values.extend(bullet.text for bullet in entry.bullets)
        values.extend(entry.technologies)
        values.extend(entry.industries)
    values.extend(entry.text for entry in targeted_cv.education if entry.visible)
    values.extend(entry.text for entry in targeted_cv.certifications if entry.visible)
    values.extend(entry.text for entry in targeted_cv.languages if entry.visible)
    return "\n".join(values)


def _audit_numbers(
    text: str,
    candidate_profile: CandidateProfessionalProfile,
    path: str,
    findings: list[TargetedCVAuditFinding],
) -> None:
    source_text = _profile_supported_text(candidate_profile)
    source_numbers = {_number_norm(value.group(0)) for value in _NUMBER_PATTERN.finditer(source_text)}
    for match in _NUMBER_PATTERN.finditer(text):
        value = _number_norm(match.group(0))
        if value and value not in source_numbers:
            _error(findings, path, f"La cifra '{match.group(0)}' no aparece respaldada por la evidencia fuente.")


def _supported_terms(
    candidate_profile: CandidateProfessionalProfile,
    job_compatibility: JobCompatibility,
) -> Iterable[str]:
    for skill in candidate_profile.skills:
        if _is_supported(skill.evidence_status):
            yield skill.name
            yield skill.normalized_name
    for match in job_compatibility.requirement_matches:
        if _is_supported(match.evidence_status) and _coverage_is_usable(match.coverage):
            yield match.requirement_name
            yield match.normalized_requirement
            yield from match.matched_candidate_items


def _job_terms(job_analysis: JobAnalysis) -> Iterable[str]:
    yield job_analysis.title
    yield from job_analysis.exact_keywords
    yield from job_analysis.technical_skills
    yield from job_analysis.soft_skills
    yield from job_analysis.leadership_skills
    yield from job_analysis.tools_and_technologies
    yield from job_analysis.industries
    yield from job_analysis.certifications
    for requirement in job_analysis.requirements:
        yield requirement.name
        yield requirement.normalized_name
        yield from requirement.exact_keywords


def _source_employment_text(employment: EmploymentEntry | None) -> str:
    if employment is None:
        return ""
    payload = employment.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False)


def _profile_supported_text(candidate_profile: CandidateProfessionalProfile) -> str:
    return candidate_profile.model_dump_json()


def _employment_key(entry: EmploymentEntry) -> tuple[str, str, str | None, str | None, str | None]:
    return (_norm(entry.employer), _norm(entry.role_title), entry.start_date, entry.end_date, _norm(entry.location or ""))


def _cv_employment_key(entry: TargetedCVExperienceEntry) -> tuple[str, str, str | None, str | None, str | None]:
    return (_norm(entry.employer), _norm(entry.source_role_title), entry.start_date, entry.end_date, _norm(entry.location or ""))


def _title_inflates_seniority(
    title: str,
    candidate_profile: CandidateProfessionalProfile,
    source: EmploymentEntry | None = None,
) -> bool:
    title_norm = _norm(title)
    requested_rank = 0
    for word, rank in _SENIORITY_RANK.items():
        if word in title_norm:
            requested_rank = max(requested_rank, rank)
    if "chief" in title_norm or "c-level" in title_norm or "vp" in title_norm:
        requested_rank = max(requested_rank, _SENIORITY_RANK["executive"])
    source_text = _norm(source.role_title if source else "")
    for word, rank in _SENIORITY_RANK.items():
        if word in source_text:
            requested_rank = max(0, requested_rank - 1 if rank >= requested_rank else requested_rank)
    supported_rank = _SENIORITY_RANK.get(str(candidate_profile.seniority), 0)
    return requested_rank > supported_rank + 1


def _coverage_is_usable(value: object) -> bool:
    return str(getattr(value, "value", value)) in {
        RequirementCoverage.FULL.value,
        RequirementCoverage.PARTIAL.value,
        RequirementCoverage.INDIRECT.value,
    }


def _is_supported(value: object) -> bool:
    return str(getattr(value, "value", value)) == EvidenceStatus.SUPPORTED.value


def _has_errors(findings: list[TargetedCVAuditFinding]) -> bool:
    return any(finding.severity == "error" for finding in findings)


def _error(findings: list[TargetedCVAuditFinding], path: str, message: str) -> None:
    findings.append(TargetedCVAuditFinding(severity="error", path=path, message=message))


def _warning(findings: list[TargetedCVAuditFinding], path: str, message: str) -> None:
    findings.append(TargetedCVAuditFinding(severity="warning", path=path, message=message))


def _norm(value: object) -> str:
    text = str(value or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text)


def _number_norm(value: str) -> str:
    return value.replace(" ", "").replace(",", ".")
