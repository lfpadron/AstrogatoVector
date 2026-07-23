"""Build, apply and validate targeted CV edit state locally."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from schemas.compatibility_models import JobCompatibility
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import TargetedCV, TargetedCVEditableValidationResult
from services.targeted_cv_audit_service import audit_targeted_cv


def build_targeted_cv_edit_state(targeted_cv: TargetedCV) -> dict[str, Any]:
    """Create Streamlit-friendly editable state from a targeted CV."""
    return {
        "edited": False,
        "professional_title": targeted_cv.header.professional_title,
        "summary": targeted_cv.summary.text,
        "selected_skills": [skill.name for skill in targeted_cv.skills],
        "experience": [
            {
                "included": entry.included,
                "display_role_title": entry.display_role_title,
                "bullets": [bullet.text for bullet in entry.bullets],
            }
            for entry in targeted_cv.experience
        ],
        "education_visible": [index for index, entry in enumerate(targeted_cv.education) if entry.visible],
        "certifications_visible": [index for index, entry in enumerate(targeted_cv.certifications) if entry.visible],
        "languages_visible": [index for index, entry in enumerate(targeted_cv.languages) if entry.visible],
    }


def apply_targeted_cv_edit_state(targeted_cv: TargetedCV, edit_state: dict[str, Any] | None) -> TargetedCV:
    """Apply explicit user edits while preserving source evidence objects."""
    if not edit_state:
        return targeted_cv

    cv = targeted_cv.model_copy(deep=True)
    header = cv.header.model_copy(update={"professional_title": _text(edit_state.get("professional_title"), cv.header.professional_title)})
    summary = cv.summary.model_copy(update={"text": _text(edit_state.get("summary"), cv.summary.text)})

    selected = {_norm(value) for value in edit_state.get("selected_skills", []) if _norm(value)}
    skills = [skill for skill in cv.skills if not selected or _norm(skill.name) in selected]
    experience_updates = edit_state.get("experience") if isinstance(edit_state.get("experience"), list) else []
    experiences = []
    for index, entry in enumerate(cv.experience):
        update = experience_updates[index] if index < len(experience_updates) and isinstance(experience_updates[index], dict) else {}
        bullets_update = update.get("bullets") if isinstance(update.get("bullets"), list) else []
        bullets = [
            bullet.model_copy(update={"text": _text(bullets_update[bullet_index], bullet.text)})
            if bullet_index < len(bullets_update)
            else bullet
            for bullet_index, bullet in enumerate(entry.bullets)
        ]
        experiences.append(
            entry.model_copy(
                update={
                    "included": bool(update.get("included", entry.included)),
                    "display_role_title": _text(update.get("display_role_title"), entry.display_role_title),
                    "bullets": bullets,
                }
            )
        )

    education_visible = set(edit_state.get("education_visible", []))
    certifications_visible = set(edit_state.get("certifications_visible", []))
    languages_visible = set(edit_state.get("languages_visible", []))
    education = [entry.model_copy(update={"visible": index in education_visible}) for index, entry in enumerate(cv.education)]
    certifications = [
        entry.model_copy(update={"visible": index in certifications_visible}) for index, entry in enumerate(cv.certifications)
    ]
    languages = [entry.model_copy(update={"visible": index in languages_visible}) for index, entry in enumerate(cv.languages)]

    edited_payload = deepcopy(edit_state)
    edited_payload.pop("_source_fingerprint", None)
    original_payload = build_targeted_cv_edit_state(targeted_cv)
    edited = edited_payload != original_payload
    return cv.model_copy(
        update={
            "content_source": "user-edited" if edited else cv.content_source,
            "header": header,
            "summary": summary,
            "skills": skills,
            "experience": experiences,
            "education": education,
            "certifications": certifications,
            "languages": languages,
        }
    )


def validate_targeted_cv_edits(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    edit_state: dict[str, Any] | None,
) -> TargetedCVEditableValidationResult:
    """Validate edited CV content without calling external services."""
    edited_cv = apply_targeted_cv_edit_state(targeted_cv, edit_state)
    audit = audit_targeted_cv(edited_cv, candidate_profile, job_analysis, job_compatibility)
    warnings = [f"{finding.path}: {finding.message}" for finding in audit.findings if finding.severity == "warning"]
    return TargetedCVEditableValidationResult(
        passed=audit.passed,
        findings=audit.findings,
        warnings=warnings,
    )


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _norm(value: object) -> str:
    return str(value or "").casefold().strip()
