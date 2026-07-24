"""Generate a four-week LinkedIn editorial plan with strict evidence boundaries."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.editorial_plan_models import (
    EDITORIAL_PLAN_PROMPT_VERSION,
    EDITORIAL_PLAN_VERSION,
    EditorialPlanGenerationResult,
    ProfessionalBrandPlan,
)
from schemas.enums import EvidenceStatus, OutputLanguage, PriorityLevel, RequirementCoverage
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.market_models import MarketKeyword, TargetMarketAnalysis
from services.editorial_plan_audit_service import audit_editorial_plan
from services.openai_service import OpenAIService
from services.prompt_loader import PromptLoadError, load_prompt

PromptLoader = Callable[[str], str]
StatusCallback = Callable[[str], None]

MAX_EDITORIAL_PLAN_INPUT_CHARS = 80_000
MAX_EDITORIAL_EXPERIENCE_ENTRIES = 16
MAX_EDITORIAL_REQUIREMENT_MATCHES = 60
MAX_EDITORIAL_AUDIT_FINDINGS = 16

EDITORIAL_PLAN_INVALID_STRUCTURE_MESSAGE = (
    "El modelo no devolvió un plan editorial válido. No se generaron resultados parciales."
)
EDITORIAL_PLAN_AUDIT_REJECTION_MESSAGE = (
    "El plan editorial fue recibido, pero no superó la auditoría local. "
    "No se utilizará porque contiene claims, repeticiones o riesgos de confidencialidad."
)


class EditorialPlanService:
    """Generate a complete professional brand editorial plan."""

    def __init__(self, openai_service: OpenAIService, *, prompt_loader: PromptLoader = load_prompt) -> None:
        self.openai_service = openai_service
        self._prompt_loader = prompt_loader

    def generate_editorial_plan(
        self,
        candidate_profile: CandidateProfessionalProfile,
        market_analysis: TargetMarketAnalysis,
        compatibility_report: CompatibilityReport,
        audit_report: AuditReport,
        output_language: OutputLanguage | str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> EditorialPlanGenerationResult:
        """Run structured generation and local audit for the editorial plan."""
        start_time = time.perf_counter()
        try:
            if status_callback:
                status_callback("Preparando plan editorial profesional...")
            system_prompt = self._prompt_loader("system_guardrails.txt")
            generation_prompt = self._prompt_loader("generate_editorial_plan.txt")
            user_input = build_editorial_plan_input(
                candidate_profile,
                market_analysis,
                compatibility_report,
                audit_report,
                output_language,
            )
            if status_callback:
                status_callback("Generando calendario de cuatro semanas...")
            result = self.openai_service.parse_structured_response(
                model_name=self.openai_service.settings.model_quality,
                system_prompt=system_prompt,
                user_prompt=f"{generation_prompt}\n\n{user_input}",
                response_model=ProfessionalBrandPlan,
            )
        except PromptLoadError:
            return EditorialPlanGenerationResult(
                success=False,
                model_used=self.openai_service.settings.model_quality,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de plan editorial.",
                retryable=False,
                prompt_version=EDITORIAL_PLAN_PROMPT_VERSION,
            )

        latency_ms = _elapsed_ms(start_time)
        if not result.success or result.parsed is None:
            return EditorialPlanGenerationResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                warnings=result.warnings,
                error_category=result.error_code,
                user_message=result.error_message or EDITORIAL_PLAN_INVALID_STRUCTURE_MESSAGE,
                retryable=result.retryable,
                prompt_version=EDITORIAL_PLAN_PROMPT_VERSION,
            )

        if status_callback:
            status_callback("Auditando evidencia, diversidad y privacidad del plan...")
        audit = audit_editorial_plan(result.parsed, candidate_profile, market_analysis, compatibility_report, audit_report)
        audit_findings = _format_audit_findings(audit.findings)
        warnings = [finding for finding in audit_findings if finding.startswith("warning:")]
        if not audit.passed:
            return EditorialPlanGenerationResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                audit_findings=audit_findings,
                warnings=warnings,
                error_category="editorial_plan_audit_failed",
                user_message=EDITORIAL_PLAN_AUDIT_REJECTION_MESSAGE,
                retryable=False,
                prompt_version=EDITORIAL_PLAN_PROMPT_VERSION,
            )

        return EditorialPlanGenerationResult(
            success=True,
            professional_brand_plan=result.parsed,
            model_used=result.model or self.openai_service.settings.model_quality,
            request_id=result.request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            audit_passed=True,
            audit_findings=audit_findings,
            warnings=warnings,
            prompt_version=EDITORIAL_PLAN_PROMPT_VERSION,
        )


def build_editorial_plan_input(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
    output_language: OutputLanguage | str,
) -> str:
    """Build the delimited reduced input for editorial plan generation."""
    payloads = {
        "candidate_evidence": _candidate_payload(candidate_profile),
        "target_market": _market_payload(market_analysis),
        "compatibility": _compatibility_payload(compatibility_report),
        "positioning_audit": _audit_payload(audit_report),
    }
    user_input = _build_input_text(payloads, output_language)
    if len(user_input) <= MAX_EDITORIAL_PLAN_INPUT_CHARS:
        return user_input
    payloads["candidate_evidence"]["employment_history"] = payloads["candidate_evidence"].get("employment_history", [])[:8]
    payloads["compatibility"]["job_compatibilities"] = payloads["compatibility"].get("job_compatibilities", [])[:4]
    return _build_input_text(payloads, output_language)[:MAX_EDITORIAL_PLAN_INPUT_CHARS]


def build_editorial_plan_input_fingerprint(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
    output_language: OutputLanguage | str,
    *,
    model_name: str,
    prompt_version: str = EDITORIAL_PLAN_PROMPT_VERSION,
) -> str:
    """Build a stable fingerprint for editorial plan input."""
    user_input = build_editorial_plan_input(
        candidate_profile,
        market_analysis,
        compatibility_report,
        audit_report,
        output_language,
    )
    payload = {
        "editorial_plan_version": EDITORIAL_PLAN_VERSION,
        "prompt_version": prompt_version,
        "model_name": model_name,
        "output_language": _language_value(output_language),
        "user_input": user_input,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate_payload(candidate_profile: CandidateProfessionalProfile) -> dict[str, Any]:
    return {
        "professional_identity": candidate_profile.professional_identity,
        "targetable_roles": candidate_profile.targetable_roles,
        "summary": candidate_profile.summary,
        "total_years_experience": candidate_profile.total_years_experience,
        "seniority": _enum_value(candidate_profile.seniority),
        "industries": candidate_profile.industries,
        "employment_history": [
            _employment_payload(item)
            for item in candidate_profile.employment_history[:MAX_EDITORIAL_EXPERIENCE_ENTRIES]
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
        "missing_information": candidate_profile.missing_information,
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


def _market_payload(market_analysis: TargetMarketAnalysis) -> dict[str, Any]:
    return {
        "target_role_family": market_analysis.target_role_family,
        "suggested_target_titles": market_analysis.suggested_target_titles,
        "dominant_seniority": _enum_value(market_analysis.dominant_seniority),
        "market_summary": market_analysis.market_summary,
        "common_responsibilities": market_analysis.common_responsibilities,
        "technical_skills": market_analysis.technical_skills,
        "leadership_skills": market_analysis.leadership_skills,
        "business_skills": market_analysis.business_skills,
        "tools_and_technologies": market_analysis.tools_and_technologies,
        "industries": market_analysis.industries,
        "differentiators": market_analysis.differentiators,
        "keywords": [_keyword_payload(keyword) for keyword in market_analysis.keywords],
    }


def _compatibility_payload(compatibility_report: CompatibilityReport) -> dict[str, Any]:
    return {
        "highest_compatibility_job_index": compatibility_report.highest_compatibility_job_index,
        "average_compatibility_score": compatibility_report.average_compatibility_score,
        "common_strengths": compatibility_report.common_strengths,
        "common_gaps": compatibility_report.common_gaps,
        "strategic_recommendations": compatibility_report.strategic_recommendations,
        "job_compatibilities": [
            {
                "job_index": job.job_index,
                "job_title": job.job_title,
                "company": job.company,
                "strengths": job.strengths,
                "critical_gaps": job.critical_gaps,
                "other_gaps": job.other_gaps,
                "risks": job.risks,
                "recommendations": job.recommendations,
                "requirement_matches": [
                    {
                        "requirement_name": match.requirement_name,
                        "normalized_requirement": match.normalized_requirement,
                        "coverage": _enum_value(match.coverage),
                        "evidence_status": _enum_value(match.evidence_status),
                        "matched_candidate_items": match.matched_candidate_items,
                        "missing_elements": match.missing_elements,
                    }
                    for match in job.requirement_matches[:MAX_EDITORIAL_REQUIREMENT_MATCHES]
                ],
            }
            for job in compatibility_report.job_compatibilities
        ],
    }


def _audit_payload(audit_report: AuditReport) -> dict[str, Any]:
    linkedin = audit_report.linkedin_positioning
    ats = audit_report.ats_estimation
    return {
        "executive_summary": audit_report.executive_summary,
        "overall_score": audit_report.overall_score,
        "linkedin_score": linkedin.score if linkedin else None,
        "ats_score": ats.score if ats else None,
        "linkedin_strengths": [_finding_payload(item) for item in (linkedin.strengths if linkedin else [])[:MAX_EDITORIAL_AUDIT_FINDINGS]],
        "linkedin_risks": [_finding_payload(item) for item in (linkedin.risks if linkedin else [])[:MAX_EDITORIAL_AUDIT_FINDINGS]],
        "ats_matched_keywords": ats.matched_keywords if ats else [],
        "ats_missing_keywords": ats.missing_keywords if ats else [],
        "quick_wins": [item.action for item in audit_report.quick_wins[:MAX_EDITORIAL_AUDIT_FINDINGS]],
        "recommendations": [item.action for item in audit_report.recommendations[:MAX_EDITORIAL_AUDIT_FINDINGS]],
    }


def _finding_payload(item: object) -> dict[str, Any]:
    return {
        "title": getattr(item, "title", None),
        "category": getattr(item, "category", None),
        "description": getattr(item, "description", None),
        "evidence": getattr(item, "evidence", []),
        "recommendation": getattr(item, "recommendation", None),
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


def _keyword_payload(keyword: MarketKeyword) -> dict[str, Any]:
    return {
        "keyword": keyword.keyword,
        "normalized_keyword": keyword.normalized_keyword,
        "frequency": keyword.frequency,
        "job_indices": keyword.job_indices,
        "category": _enum_value(keyword.category),
        "priority": _enum_value(keyword.priority),
    }


def _reference_payload(reference: EvidenceReference) -> dict[str, str]:
    return {
        "source_section": reference.source_section[:120],
        "source_excerpt": reference.source_excerpt[:240],
    }


def _build_input_text(payloads: dict[str, Any], output_language: OutputLanguage | str) -> str:
    return "\n".join(
        [
            "<ASTROGATO_VECTOR_EDITORIAL_PLAN>",
            f"<OUTPUT_LANGUAGE>{_language_value(output_language)}</OUTPUT_LANGUAGE>",
            "<CANDIDATE_EVIDENCE>",
            json.dumps(payloads["candidate_evidence"], ensure_ascii=False, indent=2),
            "</CANDIDATE_EVIDENCE>",
            "<TARGET_MARKET>",
            json.dumps(payloads["target_market"], ensure_ascii=False, indent=2),
            "</TARGET_MARKET>",
            "<COMPATIBILITY>",
            json.dumps(payloads["compatibility"], ensure_ascii=False, indent=2),
            "</COMPATIBILITY>",
            "<POSITIONING_AUDIT>",
            json.dumps(payloads["positioning_audit"], ensure_ascii=False, indent=2),
            "</POSITIONING_AUDIT>",
            "</ASTROGATO_VECTOR_EDITORIAL_PLAN>",
        ]
    )


def _is_supported(value: object) -> bool:
    return str(getattr(value, "value", value)) == EvidenceStatus.SUPPORTED.value


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _language_value(value: OutputLanguage | str) -> str:
    return str(getattr(value, "value", value))


def _format_audit_findings(findings: list[object]) -> list[str]:
    return [f"{finding.severity}: {finding.path}: {finding.message}" for finding in findings]


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))
