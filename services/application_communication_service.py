"""Generate per-vacancy application communication kits with strict boundaries."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from schemas.application_communication_models import (
    APPLICATION_COMMUNICATION_PROMPT_VERSION,
    APPLICATION_COMMUNICATION_VERSION,
    ApplicationCommunicationGenerationResult,
    ApplicationCommunicationKit,
)
from schemas.compatibility_models import JobCompatibility
from schemas.enums import EvidenceStatus, OutputLanguage, PriorityLevel, RequirementCoverage
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.market_models import JobAnalysis, JobRequirement
from schemas.targeted_cv_models import TargetedCV
from services.application_communication_audit_service import audit_application_communication_kit
from services.communication_redundancy_audit_service import audit_communication_redundancy
from services.openai_service import OpenAIService
from services.prompt_loader import PromptLoadError, load_prompt

PromptLoader = Callable[[str], str]
StatusCallback = Callable[[str], None]

MAX_APPLICATION_COMMUNICATION_INPUT_CHARS = 80_000
MAX_COMMUNICATION_EXPERIENCE_ENTRIES = 12
MAX_COMMUNICATION_REQUIREMENT_MATCHES = 50

APPLICATION_COMMUNICATION_INVALID_STRUCTURE_MESSAGE = (
    "El modelo no devolvió un kit de comunicación válido. No se generaron resultados parciales."
)
APPLICATION_COMMUNICATION_AUDIT_REJECTION_MESSAGE = (
    "El kit fue recibido, pero no superó la auditoría local de evidencia o redundancia. "
    "No se utilizará porque contiene afirmaciones, mezclas de vacante o repeticiones no seguras."
)


class ApplicationCommunicationService:
    """Generate one application communication kit for one analyzed vacancy."""

    def __init__(self, openai_service: OpenAIService, *, prompt_loader: PromptLoader = load_prompt) -> None:
        self.openai_service = openai_service
        self._prompt_loader = prompt_loader

    def generate_communication_kit(
        self,
        candidate_profile: CandidateProfessionalProfile,
        job_analysis: JobAnalysis,
        job_compatibility: JobCompatibility,
        targeted_cv: TargetedCV,
        output_language: OutputLanguage | str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> ApplicationCommunicationGenerationResult:
        """Run structured generation for one vacancy communication kit."""
        start_time = time.perf_counter()
        try:
            if status_callback:
                status_callback(f"Preparando comunicación para vacante {job_analysis.job_index}...")
            system_prompt = self._prompt_loader("system_guardrails.txt")
            generation_prompt = self._prompt_loader("generate_application_communications.txt")
            user_input = build_application_communication_input(
                candidate_profile,
                job_analysis,
                job_compatibility,
                targeted_cv,
                output_language,
            )
            if status_callback:
                status_callback(f"Generando kit de postulación para {job_analysis.title}...")
            result = self.openai_service.parse_structured_response(
                model_name=self.openai_service.settings.model_quality,
                system_prompt=system_prompt,
                user_prompt=f"{generation_prompt}\n\n{user_input}",
                response_model=ApplicationCommunicationKit,
            )
        except PromptLoadError:
            return ApplicationCommunicationGenerationResult(
                success=False,
                model_used=self.openai_service.settings.model_quality,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de comunicación por vacante.",
                retryable=False,
                prompt_version=APPLICATION_COMMUNICATION_PROMPT_VERSION,
            )

        latency_ms = _elapsed_ms(start_time)
        if not result.success or result.parsed is None:
            return ApplicationCommunicationGenerationResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                redundancy_audit_passed=False,
                warnings=result.warnings,
                error_category=result.error_code,
                user_message=result.error_message or APPLICATION_COMMUNICATION_INVALID_STRUCTURE_MESSAGE,
                retryable=result.retryable,
                prompt_version=APPLICATION_COMMUNICATION_PROMPT_VERSION,
            )

        if status_callback:
            status_callback(f"Auditando comunicación para vacante {job_analysis.job_index}...")
        audit = audit_application_communication_kit(
            result.parsed,
            candidate_profile,
            job_analysis,
            job_compatibility,
            targeted_cv,
        )
        redundancy = audit_communication_redundancy(result.parsed, targeted_cv)
        audit_findings = _format_audit_findings(audit.findings)
        redundancy_findings = _format_audit_findings(redundancy.findings)
        warnings = [
            *[finding for finding in audit_findings if finding.startswith("warning:")],
            *[finding for finding in redundancy_findings if finding.startswith("warning:")],
        ]
        if not audit.passed or not redundancy.passed:
            return ApplicationCommunicationGenerationResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=audit.passed,
                redundancy_audit_passed=redundancy.passed,
                audit_findings=audit_findings,
                redundancy_findings=redundancy_findings,
                warnings=warnings,
                error_category="application_communication_audit_failed",
                user_message=APPLICATION_COMMUNICATION_AUDIT_REJECTION_MESSAGE,
                retryable=False,
                prompt_version=APPLICATION_COMMUNICATION_PROMPT_VERSION,
            )

        return ApplicationCommunicationGenerationResult(
            success=True,
            communication_kit=result.parsed,
            model_used=result.model or self.openai_service.settings.model_quality,
            request_id=result.request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            audit_passed=True,
            redundancy_audit_passed=True,
            audit_findings=audit_findings,
            redundancy_findings=redundancy_findings,
            warnings=warnings,
            prompt_version=APPLICATION_COMMUNICATION_PROMPT_VERSION,
        )


def build_application_communication_input(
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    output_language: OutputLanguage | str,
) -> str:
    """Build the delimited reduced input for one application communication kit."""
    candidate_payload = _candidate_payload(candidate_profile, targeted_cv)
    job_payload = _job_payload(job_analysis)
    compatibility_payload = _compatibility_payload(job_compatibility)
    targeted_cv_payload = _targeted_cv_payload(targeted_cv)
    user_input = _build_input_text(
        candidate_payload,
        job_payload,
        compatibility_payload,
        targeted_cv_payload,
        output_language,
    )
    if len(user_input) <= MAX_APPLICATION_COMMUNICATION_INPUT_CHARS:
        return user_input
    candidate_payload["employment_history"] = candidate_payload.get("employment_history", [])[:6]
    compatibility_payload["requirement_matches"] = compatibility_payload.get("requirement_matches", [])[:25]
    targeted_cv_payload["experience"] = targeted_cv_payload.get("experience", [])[:6]
    return _build_input_text(
        candidate_payload,
        job_payload,
        compatibility_payload,
        targeted_cv_payload,
        output_language,
    )[:MAX_APPLICATION_COMMUNICATION_INPUT_CHARS]


def build_application_communication_input_fingerprint(
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    output_language: OutputLanguage | str,
    *,
    model_name: str,
    prompt_version: str = APPLICATION_COMMUNICATION_PROMPT_VERSION,
) -> str:
    """Build a stable fingerprint for one communication generation input."""
    user_input = build_application_communication_input(
        candidate_profile,
        job_analysis,
        job_compatibility,
        targeted_cv,
        output_language,
    )
    payload = {
        "application_communication_version": APPLICATION_COMMUNICATION_VERSION,
        "prompt_version": prompt_version,
        "model_name": model_name,
        "output_language": _language_value(output_language),
        "user_input": user_input,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate_payload(
    candidate_profile: CandidateProfessionalProfile,
    targeted_cv: TargetedCV,
) -> dict[str, Any]:
    used_employers = {entry.employer for entry in targeted_cv.experience if entry.included}
    return {
        "professional_identity": candidate_profile.professional_identity,
        "targetable_roles": candidate_profile.targetable_roles,
        "summary": candidate_profile.summary,
        "total_years_experience": candidate_profile.total_years_experience,
        "seniority": _enum_value(candidate_profile.seniority),
        "industries": candidate_profile.industries,
        "available_contact": {
            "email": targeted_cv.header.email,
            "phone": targeted_cv.header.phone,
            "linkedin_url": targeted_cv.header.linkedin_url,
            "note": "No incluir teléfono/email en mensaje para recruiter por defecto.",
        },
        "employment_history": [
            _employment_payload(item)
            for item in candidate_profile.employment_history[:MAX_COMMUNICATION_EXPERIENCE_ENTRIES]
            if item.employer in used_employers or not used_employers
        ],
        "supported_skills": [_skill_payload(skill) for skill in candidate_profile.skills if _is_supported(skill.evidence_status)],
        "leadership_capabilities": [
            _evidence_payload(item) for item in candidate_profile.leadership_capabilities if _is_supported(item.status)
        ],
        "education": [_evidence_payload(item) for item in candidate_profile.education if _is_supported(item.status)],
        "certifications": [_evidence_payload(item) for item in candidate_profile.certifications if _is_supported(item.status)],
        "languages": [_evidence_payload(item) for item in candidate_profile.languages if _is_supported(item.status)],
        "achievements": [
            _achievement_payload(item) for item in candidate_profile.achievements if _is_supported(item.evidence_status)
        ],
        "ambiguities": candidate_profile.ambiguities,
        "conflicts": candidate_profile.conflicts,
    }


def _employment_payload(employment: EmploymentEntry) -> dict[str, Any]:
    return {
        "employer": employment.employer,
        "role_title": employment.role_title,
        "start_date": employment.start_date,
        "end_date": employment.end_date,
        "is_current": employment.is_current,
        "location": employment.location,
        "responsibilities": [
            _evidence_payload(item) for item in employment.responsibilities if _is_supported(item.status)
        ],
        "achievements": [
            _achievement_payload(item) for item in employment.achievements if _is_supported(item.evidence_status)
        ],
        "technologies": [_skill_payload(item) for item in employment.technologies if _is_supported(item.evidence_status)],
        "industries": employment.industries,
    }


def _job_payload(job_analysis: JobAnalysis) -> dict[str, Any]:
    return {
        "job_index": job_analysis.job_index,
        "title": job_analysis.title,
        "company": job_analysis.company,
        "inferred_seniority": _enum_value(job_analysis.inferred_seniority),
        "role_summary": job_analysis.role_summary,
        "responsibilities": job_analysis.responsibilities,
        "requirements": [_requirement_payload(item) for item in job_analysis.requirements],
        "technical_skills": job_analysis.technical_skills,
        "soft_skills": job_analysis.soft_skills,
        "leadership_skills": job_analysis.leadership_skills,
        "tools_and_technologies": job_analysis.tools_and_technologies,
        "industries": job_analysis.industries,
        "education_requirements": job_analysis.education_requirements,
        "language_requirements": job_analysis.language_requirements,
        "certifications": job_analysis.certifications,
        "exact_keywords": job_analysis.exact_keywords,
    }


def _compatibility_payload(job_compatibility: JobCompatibility) -> dict[str, Any]:
    return {
        "job_index": job_compatibility.job_index,
        "job_title": job_compatibility.job_title,
        "company": job_compatibility.company,
        "compatibility_score": job_compatibility.compatibility_score,
        "compatibility_band": _enum_value(job_compatibility.compatibility_band),
        "summary": job_compatibility.summary,
        "strengths": job_compatibility.strengths,
        "critical_gaps": job_compatibility.critical_gaps,
        "other_gaps": job_compatibility.other_gaps,
        "risks": job_compatibility.risks,
        "recommendations": job_compatibility.recommendations,
        "requirement_matches": [
            {
                "requirement_name": match.requirement_name,
                "normalized_requirement": match.normalized_requirement,
                "category": _enum_value(match.category),
                "required": match.required,
                "priority": _enum_value(match.priority),
                "coverage": _enum_value(match.coverage),
                "evidence_status": _enum_value(match.evidence_status),
                "matched_candidate_items": match.matched_candidate_items,
                "missing_elements": match.missing_elements,
                "candidate_evidence": [_evidence_payload(item) for item in match.candidate_evidence],
                "explanation": match.explanation,
                "recommendation": match.recommendation,
            }
            for match in sorted(
                job_compatibility.requirement_matches,
                key=lambda item: (_priority_order(item.priority), item.required is False, item.normalized_requirement),
            )[:MAX_COMMUNICATION_REQUIREMENT_MATCHES]
        ],
    }


def _targeted_cv_payload(targeted_cv: TargetedCV) -> dict[str, Any]:
    return {
        "target_job_index": targeted_cv.target_job_index,
        "target_job_title": targeted_cv.target_job_title,
        "target_company": targeted_cv.target_company,
        "professional_title": targeted_cv.header.professional_title,
        "summary": targeted_cv.summary.text,
        "selected_skills": [skill.name for skill in sorted(targeted_cv.skills, key=lambda item: item.priority)],
        "experience": [
            {
                "source_role_title": entry.source_role_title,
                "display_role_title": entry.display_role_title,
                "employer": entry.employer,
                "included": entry.included,
                "bullets": [bullet.text for bullet in entry.bullets],
                "technologies": entry.technologies,
                "industries": entry.industries,
            }
            for entry in targeted_cv.experience
        ],
        "ats_keywords_used": targeted_cv.ats_keywords_used,
        "ats_keywords_missing": targeted_cv.ats_keywords_missing,
        "overall_review_notes": targeted_cv.overall_review_notes,
        "cv_version": targeted_cv.cv_version,
    }


def _evidence_payload(item: EvidenceItem) -> dict[str, Any]:
    return {
        "statement": item.statement,
        "status": _enum_value(item.status),
        "category": _enum_value(item.category),
        "confidence": item.confidence,
        "references": [_reference_payload(reference) for reference in item.references[:2]],
        "notes": item.notes,
    }


def _achievement_payload(achievement: Achievement) -> dict[str, Any]:
    return {
        "description": achievement.description,
        "measurable_result": achievement.measurable_result,
        "evidence_status": _enum_value(achievement.evidence_status),
        "references": [_reference_payload(reference) for reference in achievement.references[:2]],
    }


def _skill_payload(skill: CandidateSkill) -> dict[str, Any]:
    return {
        "name": skill.name,
        "normalized_name": skill.normalized_name,
        "category": _enum_value(skill.category),
        "evidence_status": _enum_value(skill.evidence_status),
        "confidence": skill.confidence,
        "years_experience": skill.years_experience,
        "references": [_reference_payload(reference) for reference in skill.references[:2]],
    }


def _requirement_payload(requirement: JobRequirement) -> dict[str, Any]:
    return {
        "name": requirement.name,
        "normalized_name": requirement.normalized_name,
        "category": _enum_value(requirement.category),
        "description": requirement.description,
        "required": requirement.required,
        "importance": _enum_value(requirement.importance),
        "exact_keywords": requirement.exact_keywords,
    }


def _reference_payload(reference: EvidenceReference) -> dict[str, str]:
    return {
        "source_section": reference.source_section[:120],
        "source_excerpt": reference.source_excerpt[:240],
    }


def _build_input_text(
    candidate_payload: dict[str, Any],
    job_payload: dict[str, Any],
    compatibility_payload: dict[str, Any],
    targeted_cv_payload: dict[str, Any],
    output_language: OutputLanguage | str,
) -> str:
    return "\n".join(
        [
            "<ASTROGATO_VECTOR_APPLICATION_COMMUNICATION>",
            f"<OUTPUT_LANGUAGE>{_language_value(output_language)}</OUTPUT_LANGUAGE>",
            "<CANDIDATE_EVIDENCE>",
            json.dumps(candidate_payload, ensure_ascii=False, indent=2),
            "</CANDIDATE_EVIDENCE>",
            "<TARGET_JOB>",
            json.dumps(job_payload, ensure_ascii=False, indent=2),
            "</TARGET_JOB>",
            "<COMPATIBILITY>",
            json.dumps(compatibility_payload, ensure_ascii=False, indent=2),
            "</COMPATIBILITY>",
            "<TARGETED_CV_SUMMARY>",
            json.dumps(targeted_cv_payload, ensure_ascii=False, indent=2),
            "</TARGETED_CV_SUMMARY>",
            "</ASTROGATO_VECTOR_APPLICATION_COMMUNICATION>",
        ]
    )


def _priority_order(value: object) -> int:
    normalized = _enum_value(value)
    order = {
        PriorityLevel.CRITICAL.value: 0,
        PriorityLevel.HIGH.value: 1,
        PriorityLevel.MEDIUM.value: 2,
        PriorityLevel.LOW.value: 3,
    }
    return order.get(normalized, 4)


def _is_supported(value: object) -> bool:
    return str(getattr(value, "value", value)) == EvidenceStatus.SUPPORTED.value


def _coverage_is_usable(value: object) -> bool:
    return str(getattr(value, "value", value)) in {
        RequirementCoverage.FULL.value,
        RequirementCoverage.PARTIAL.value,
        RequirementCoverage.INDIRECT.value,
    }


def _format_audit_findings(findings: list[object]) -> list[str]:
    return [f"{finding.severity}: {finding.path}: {finding.message}" for finding in findings]


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _language_value(value: OutputLanguage | str) -> str:
    return str(getattr(value, "value", value))


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))
