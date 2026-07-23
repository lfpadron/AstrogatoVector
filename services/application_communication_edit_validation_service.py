"""Build, apply and validate editable application communication state locally."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from schemas.application_communication_models import (
    ApplicationCommunicationAuditFinding,
    ApplicationCommunicationEditValidationResult,
    ApplicationCommunicationKit,
)
from schemas.compatibility_models import JobCompatibility
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import TargetedCV
from services.application_communication_audit_service import (
    audit_application_communication_kit,
    communication_text,
    count_words,
)
from services.communication_redundancy_audit_service import audit_communication_redundancy

_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s?%?|\b\d{4}\b")
_CAPITALIZED_PAIR_PATTERN = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}\b")
_SAFE_NAME_WORDS = {
    "Carta Presentación",
    "Mensaje Recruiter",
    "Project Manager",
    "Program Manager",
    "Senior Project",
    "Empresa Demo",
}


def build_application_communication_edit_state(kit: ApplicationCommunicationKit) -> dict[str, Any]:
    """Create Streamlit-friendly editable state for one communication kit."""
    return {
        "edited": False,
        "cover_letter_greeting": kit.cover_letter.greeting,
        "cover_letter_full_text": kit.cover_letter.full_text,
        "cover_letter_sign_off": kit.cover_letter.sign_off,
        "recruiter_message": kit.recruiter_message.message,
        "subject_options": list(kit.application_email.subject_options),
        "application_email_greeting": kit.application_email.greeting,
        "application_email_full_text": kit.application_email.full_text,
        "application_email_sign_off": kit.application_email.sign_off,
        "attachments_mentioned": list(kit.application_email.attachments_mentioned),
    }


def apply_application_communication_edit_state(
    kit: ApplicationCommunicationKit,
    edit_state: dict[str, Any] | None,
) -> ApplicationCommunicationKit:
    """Apply explicit user edits while preserving original claims and metadata."""
    if not edit_state:
        return kit
    updated = kit.model_copy(deep=True)
    cover_full_text = _text(edit_state.get("cover_letter_full_text"), updated.cover_letter.full_text)
    recruiter_message = _text(edit_state.get("recruiter_message"), updated.recruiter_message.message)
    email_full_text = _text(edit_state.get("application_email_full_text"), updated.application_email.full_text)
    subjects = _subjects(edit_state.get("subject_options"), updated.application_email.subject_options)
    cover = updated.cover_letter.model_copy(
        update={
            "greeting": _text(edit_state.get("cover_letter_greeting"), updated.cover_letter.greeting),
            "full_text": cover_full_text,
            "sign_off": _text(edit_state.get("cover_letter_sign_off"), updated.cover_letter.sign_off),
            "word_count": count_words(cover_full_text),
        }
    )
    recruiter = updated.recruiter_message.model_copy(
        update={
            "message": recruiter_message,
            "character_count": len(recruiter_message.strip()),
        }
    )
    email = updated.application_email.model_copy(
        update={
            "subject_options": subjects,
            "greeting": _text(edit_state.get("application_email_greeting"), updated.application_email.greeting),
            "full_text": email_full_text,
            "sign_off": _text(edit_state.get("application_email_sign_off"), updated.application_email.sign_off),
            "attachments_mentioned": _string_list(edit_state.get("attachments_mentioned")),
            "word_count": count_words(email_full_text),
        }
    )
    return updated.model_copy(
        update={
            "cover_letter": cover,
            "recruiter_message": recruiter,
            "application_email": email,
            "subject_options": subjects,
        }
    )


def validate_application_communication_edits(
    original_kit: ApplicationCommunicationKit,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    edit_state: dict[str, Any] | None,
) -> ApplicationCommunicationEditValidationResult:
    """Validate edited communication content without calling OpenAI."""
    edited = apply_application_communication_edit_state(original_kit, edit_state)
    audit = audit_application_communication_kit(edited, candidate_profile, job_analysis, job_compatibility, targeted_cv)
    redundancy = audit_communication_redundancy(edited, targeted_cv)
    findings = [*audit.findings, *redundancy.findings]
    warnings = [f"{finding.path}: {finding.message}" for finding in findings if finding.severity == "warning"]
    findings.extend(_audit_new_edit_claims(original_kit, edited, candidate_profile, job_analysis, targeted_cv))
    return ApplicationCommunicationEditValidationResult(
        passed=not any(finding.severity == "error" for finding in findings),
        findings=findings,
        warnings=warnings,
    )


def edit_state_changed(kit: ApplicationCommunicationKit, edit_state: dict[str, Any] | None) -> bool:
    """Return whether editable state differs from the original kit."""
    if not edit_state:
        return False
    edited_payload = deepcopy(edit_state)
    edited_payload.pop("edited", None)
    edited_payload.pop("_source_fingerprint", None)
    original_payload = build_application_communication_edit_state(kit)
    original_payload.pop("edited", None)
    return edited_payload != original_payload


def _audit_new_edit_claims(
    original: ApplicationCommunicationKit,
    edited: ApplicationCommunicationKit,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    targeted_cv: TargetedCV,
) -> list[ApplicationCommunicationAuditFinding]:
    findings: list[ApplicationCommunicationAuditFinding] = []
    original_text = communication_text(original)
    edited_text = communication_text(edited)
    supported_source = "\n".join(
        [
            candidate_profile.model_dump_json(),
            job_analysis.model_dump_json(),
            targeted_cv.model_dump_json(),
        ]
    )
    original_numbers = {_number_norm(match.group(0)) for match in _NUMBER_PATTERN.finditer(original_text)}
    supported_numbers = {_number_norm(match.group(0)) for match in _NUMBER_PATTERN.finditer(supported_source)}
    for match in _NUMBER_PATTERN.finditer(edited_text):
        value = _number_norm(match.group(0))
        if value not in original_numbers and value not in supported_numbers:
            _error(findings, "edited_text", f"La edición agregó una cifra sin respaldo: {match.group(0)}.")

    unsupported_tools = {
        _norm(tool)
        for tool in job_analysis.tools_and_technologies
        if _norm(tool) and _norm(tool) not in _norm(candidate_profile.model_dump_json() + targeted_cv.model_dump_json())
    }
    edited_norm = _norm(edited_text)
    original_norm = _norm(original_text)
    for tool in unsupported_tools:
        if tool in edited_norm and tool not in original_norm:
            _error(findings, "edited_text", "La edición agregó una herramienta de la vacante sin respaldo profesional.")

    allowed_companies = {
        _norm(job_analysis.company or ""),
        *(_norm(entry.employer) for entry in candidate_profile.employment_history),
    }
    for phrase in _CAPITALIZED_PAIR_PATTERN.findall(edited_text):
        phrase_norm = _norm(phrase)
        if phrase in _SAFE_NAME_WORDS or phrase_norm in allowed_companies or phrase_norm in original_norm:
            continue
        if any(term in phrase_norm for term in ("estimado", "dear", "hola", "equipo", "reclutamiento")):
            continue
        _warning(findings, "edited_text", "La edición podría haber agregado un nombre propio no verificado.")

    for attachment in edited.application_email.attachments_mentioned:
        normalized = _norm(attachment)
        if normalized and not any(term in normalized for term in ("cv", "curriculum", "currículum", "carta")):
            _warning(findings, "application_email.attachments_mentioned", "Revisa adjuntos mencionados no generados por la app.")
    return findings


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _subjects(value: object, fallback: list[str]) -> list[str]:
    values = _string_list(value)
    return values[:3] if values else fallback


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _number_norm(value: str) -> str:
    return value.replace(" ", "").replace(",", ".")


def _norm(value: object) -> str:
    return str(value or "").casefold().strip()


def _error(findings: list[ApplicationCommunicationAuditFinding], path: str, message: str) -> None:
    findings.append(ApplicationCommunicationAuditFinding(severity="error", path=path, message=message))


def _warning(findings: list[ApplicationCommunicationAuditFinding], path: str, message: str) -> None:
    findings.append(ApplicationCommunicationAuditFinding(severity="warning", path=path, message=message))
