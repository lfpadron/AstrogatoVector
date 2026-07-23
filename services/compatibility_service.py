"""Compatibility analysis with semantic OpenAI evaluation and local scoring."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from schemas.compatibility_analysis_models import CompatibilityAnalysisResult, CompatibilitySemanticEvaluation
from schemas.compatibility_models import COMPATIBILITY_DIMENSION_WEIGHTS, COMPATIBILITY_METHODOLOGY_VERSION
from schemas.enums import OutputLanguage, PriorityLevel
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EvidenceItem,
    EvidenceReference,
)
from schemas.market_models import JobRequirement, TargetMarketAnalysis
from services.compatibility_audit_service import (
    MATH_AUDIT_ERROR_MESSAGE,
    SEMANTIC_AUDIT_EVIDENCE_ERROR_MESSAGE,
    audit_compatibility_report,
    audit_semantic_compatibility,
)
from services.compatibility_scoring_service import (
    COVERAGE_POINTS,
    EVIDENCE_STATUS_FACTORS,
    REQUIREMENT_PRIORITY_WEIGHTS,
    REQUIRED_REQUIREMENT_MULTIPLIER,
    PREFERRED_REQUIREMENT_MULTIPLIER,
    CRITICAL_REQUIRED_MISSING_PENALTY,
    MAX_CRITICAL_MISSING_PENALTY,
    SENIORITY_GAP_PENALTY,
    MANDATORY_LANGUAGE_MISSING_PENALTY,
    SCORING_CONSTANTS_VERSION,
    CompatibilityScoringService,
)
from services.openai_service import OpenAIService
from services.prompt_loader import PromptLoadError, load_prompt
from utils.constants import MAX_REFERENCES_PER_ITEM_FOR_GENERATION

PromptLoader = Callable[[str], str]
StatusCallback = Callable[[str], None]

COMPATIBILITY_PROMPT_VERSION = "1.0"
COMPATIBILITY_INPUT_MAX_CHARS = 90_000
COMPATIBILITY_TRUNCATION_WARNING = (
    "La evidencia resumida para calcular compatibilidad superó el tamaño recomendado. "
    "Se usó una versión reducida y el resultado requiere revisión adicional."
)
COMPATIBILITY_INVALID_STRUCTURE_MESSAGE = (
    "El modelo no devolvió una evaluación semántica de compatibilidad válida. No se generaron resultados parciales."
)


@dataclass(frozen=True)
class CompatibilityAnalysisPayload:
    """Prepared payload for compatibility semantic evaluation."""

    user_input: str
    warnings: list[str]


class CompatibilityService:
    """Analyze candidate/job compatibility while keeping scoring deterministic."""

    def __init__(
        self,
        openai_service: OpenAIService,
        *,
        prompt_loader: PromptLoader = load_prompt,
        scoring_service: CompatibilityScoringService | None = None,
    ) -> None:
        self.openai_service = openai_service
        self._prompt_loader = prompt_loader
        self._scoring_service = scoring_service or CompatibilityScoringService()

    def analyze_compatibility(
        self,
        candidate_profile: CandidateProfessionalProfile,
        market_analysis: TargetMarketAnalysis,
        output_language: OutputLanguage | str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> CompatibilityAnalysisResult:
        """Run semantic compatibility evaluation, scoring and audit."""
        start_time = time.perf_counter()
        warnings: list[str] = []

        try:
            if status_callback:
                status_callback("Preparando la comparación…")
            system_prompt = self._prompt_loader("system_guardrails.txt")
            compatibility_prompt = self._prompt_loader("compatibility_analysis.txt")
            payload = prepare_compatibility_analysis_payload(candidate_profile, market_analysis, output_language)
            warnings.extend(payload.warnings)

            if status_callback:
                status_callback("Evaluando requisitos por vacante…")
            result = self.openai_service.parse_structured_response(
                model_name=self.openai_service.settings.model_quality,
                system_prompt=system_prompt,
                user_prompt=f"{compatibility_prompt}\n\n{payload.user_input}",
                response_model=CompatibilitySemanticEvaluation,
            )
        except PromptLoadError:
            return CompatibilityAnalysisResult(
                success=False,
                model_used=self.openai_service.settings.model_quality,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de análisis de compatibilidad.",
                retryable=False,
                prompt_version=COMPATIBILITY_PROMPT_VERSION,
                methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            )

        latency_ms = _elapsed_ms(start_time)
        if not result.success or result.parsed is None:
            return CompatibilityAnalysisResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                warnings=_unique_preserving_order([*warnings, *result.warnings]),
                error_category=result.error_code,
                user_message=result.error_message or COMPATIBILITY_INVALID_STRUCTURE_MESSAGE,
                retryable=result.retryable,
                prompt_version=COMPATIBILITY_PROMPT_VERSION,
                methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            )

        semantic_audit = audit_semantic_compatibility(result.parsed, candidate_profile, market_analysis)
        semantic_findings = _format_audit_findings(semantic_audit.findings)
        warnings.extend(finding for finding in semantic_findings if finding.startswith("warning:"))
        if not semantic_audit.passed:
            return CompatibilityAnalysisResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                audit_findings=semantic_findings,
                warnings=_unique_preserving_order(warnings),
                error_category="compatibility_semantic_audit_failed",
                user_message=SEMANTIC_AUDIT_EVIDENCE_ERROR_MESSAGE,
                retryable=False,
                prompt_version=COMPATIBILITY_PROMPT_VERSION,
                methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            )

        try:
            if status_callback:
                status_callback("Calculando las seis dimensiones…")
            report = self._scoring_service.calculate_report(
                result.parsed,
                market_analysis,
                candidate_profile,
                output_language,
            )
        except (ValueError, ValidationError):
            return CompatibilityAnalysisResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                audit_findings=semantic_findings,
                warnings=_unique_preserving_order(warnings),
                error_category="compatibility_scoring_failed",
                user_message=MATH_AUDIT_ERROR_MESSAGE,
                retryable=False,
                prompt_version=COMPATIBILITY_PROMPT_VERSION,
                methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            )

        if status_callback:
            status_callback("Identificando fortalezas y brechas…")
        if status_callback:
            status_callback("Validando la fórmula y la evidencia…")
        report_audit = audit_compatibility_report(report, result.parsed, market_analysis)
        report_findings = _format_audit_findings(report_audit.findings)
        warnings.extend(finding for finding in report_findings if finding.startswith("warning:"))
        audit_findings = [*semantic_findings, *report_findings]
        if not report_audit.passed:
            return CompatibilityAnalysisResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                audit_passed=False,
                audit_findings=audit_findings,
                warnings=_unique_preserving_order(warnings),
                error_category="compatibility_report_audit_failed",
                user_message=MATH_AUDIT_ERROR_MESSAGE,
                retryable=False,
                prompt_version=COMPATIBILITY_PROMPT_VERSION,
                methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            )

        return CompatibilityAnalysisResult(
            success=True,
            semantic_evaluation=result.parsed,
            compatibility_report=report,
            model_used=result.model or self.openai_service.settings.model_quality,
            request_id=result.request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            audit_passed=True,
            audit_findings=audit_findings,
            warnings=_unique_preserving_order(warnings),
            prompt_version=COMPATIBILITY_PROMPT_VERSION,
            methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
        )


def prepare_compatibility_analysis_payload(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
) -> CompatibilityAnalysisPayload:
    """Build the reduced, delimited compatibility payload."""
    warnings: list[str] = []
    candidate_payload = _candidate_payload(candidate_profile)
    jobs_payload = _jobs_payload(market_analysis)
    user_input = _build_compatibility_analysis_text(candidate_payload, jobs_payload, output_language)
    if len(user_input) > COMPATIBILITY_INPUT_MAX_CHARS:
        warnings.append(COMPATIBILITY_TRUNCATION_WARNING)
        candidate_payload["employment_history"] = candidate_payload.get("employment_history", [])[:20]
        jobs_payload = jobs_payload[:6]
        user_input = _build_compatibility_analysis_text(candidate_payload, jobs_payload, output_language)
    if len(user_input) > COMPATIBILITY_INPUT_MAX_CHARS:
        user_input = _reduce_payload_text(user_input, COMPATIBILITY_INPUT_MAX_CHARS)
    return CompatibilityAnalysisPayload(user_input=user_input, warnings=_unique_preserving_order(warnings))


def build_compatibility_analysis_input(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
) -> str:
    """Return the safe, delimited user message for compatibility analysis."""
    return prepare_compatibility_analysis_payload(candidate_profile, market_analysis, output_language).user_input


def build_compatibility_analysis_fingerprint(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
    *,
    model_name: str,
    prompt_version: str = COMPATIBILITY_PROMPT_VERSION,
    methodology_version: str = COMPATIBILITY_METHODOLOGY_VERSION,
) -> str:
    """Build a local fingerprint from reduced evidence, jobs and scoring constants."""
    payload = prepare_compatibility_analysis_payload(candidate_profile, market_analysis, output_language)
    constants = {
        "methodology_version": methodology_version,
        "scoring_constants_version": SCORING_CONSTANTS_VERSION,
        "dimension_weights": COMPATIBILITY_DIMENSION_WEIGHTS,
        "coverage_points": {str(key): value for key, value in COVERAGE_POINTS.items()},
        "evidence_status_factors": EVIDENCE_STATUS_FACTORS,
        "priority_weights": REQUIREMENT_PRIORITY_WEIGHTS,
        "required_multiplier": REQUIRED_REQUIREMENT_MULTIPLIER,
        "preferred_multiplier": PREFERRED_REQUIREMENT_MULTIPLIER,
        "critical_required_missing_penalty": CRITICAL_REQUIRED_MISSING_PENALTY,
        "max_critical_missing_penalty": MAX_CRITICAL_MISSING_PENALTY,
        "seniority_gap_penalty": SENIORITY_GAP_PENALTY,
        "mandatory_language_missing_penalty": MANDATORY_LANGUAGE_MISSING_PENALTY,
    }
    hasher = hashlib.sha256()
    for value in (
        _language_value(output_language),
        model_name,
        prompt_version,
        methodology_version,
        json.dumps(constants, ensure_ascii=False, sort_keys=True),
        payload.user_input,
    ):
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _candidate_payload(candidate_profile: CandidateProfessionalProfile) -> dict[str, Any]:
    return {
        "professional_identity": candidate_profile.professional_identity,
        "targetable_roles": candidate_profile.targetable_roles,
        "summary": candidate_profile.summary,
        "total_years_experience": candidate_profile.total_years_experience,
        "seniority": _enum_value(candidate_profile.seniority),
        "industries": candidate_profile.industries,
        "employment_history": [
            {
                "employer": employment.employer,
                "role_title": employment.role_title,
                "start_date": employment.start_date,
                "end_date": employment.end_date,
                "is_current": employment.is_current,
                "responsibilities": [_evidence_item_payload(item) for item in employment.responsibilities],
                "achievements": [_achievement_payload(achievement) for achievement in employment.achievements],
                "technologies": [_skill_payload(skill) for skill in employment.technologies],
                "industries": employment.industries,
            }
            for employment in candidate_profile.employment_history
        ],
        "skills": [_skill_payload(skill) for skill in candidate_profile.skills],
        "leadership": [_evidence_item_payload(item) for item in candidate_profile.leadership_capabilities],
        "education": [_evidence_item_payload(item) for item in candidate_profile.education],
        "certifications": [_evidence_item_payload(item) for item in candidate_profile.certifications],
        "languages": [_evidence_item_payload(item) for item in candidate_profile.languages],
        "achievements": [_achievement_payload(achievement) for achievement in candidate_profile.achievements],
        "ambiguities": candidate_profile.ambiguities,
        "conflicts": candidate_profile.conflicts,
        "missing_information": candidate_profile.missing_information,
    }


def _jobs_payload(market_analysis: TargetMarketAnalysis) -> list[dict[str, Any]]:
    return [
        {
            "job_index": job.job_index,
            "title": job.title,
            "company": job.company,
            "inferred_seniority": _enum_value(job.inferred_seniority),
            "role_summary": job.role_summary,
            "responsibilities": job.responsibilities,
            "requirements": [_requirement_payload(requirement) for requirement in job.requirements],
            "technical_skills": job.technical_skills,
            "soft_skills": job.soft_skills,
            "leadership_skills": job.leadership_skills,
            "tools_and_technologies": job.tools_and_technologies,
            "industries": job.industries,
            "education_requirements": job.education_requirements,
            "language_requirements": job.language_requirements,
            "certifications": job.certifications,
            "exact_keywords": job.exact_keywords,
        }
        for job in sorted(market_analysis.job_analyses, key=lambda item: item.job_index)
    ]


def _evidence_item_payload(item: EvidenceItem) -> dict[str, Any]:
    return {
        "statement": item.statement,
        "status": _enum_value(item.status),
        "category": _enum_value(item.category),
        "confidence": item.confidence,
        "references": _references_payload(item.references),
        "notes": item.notes,
    }


def _achievement_payload(achievement: Achievement) -> dict[str, Any]:
    return {
        "description": achievement.description,
        "measurable_result": achievement.measurable_result,
        "evidence_status": _enum_value(achievement.evidence_status),
        "references": _references_payload(achievement.references),
    }


def _skill_payload(skill: CandidateSkill) -> dict[str, Any]:
    return {
        "name": skill.name,
        "normalized_name": skill.normalized_name,
        "category": _enum_value(skill.category),
        "evidence_status": _enum_value(skill.evidence_status),
        "confidence": skill.confidence,
        "years_experience": skill.years_experience,
        "references": _references_payload(skill.references),
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


def _references_payload(references: list[EvidenceReference]) -> list[dict[str, str]]:
    seen = set()
    payload = []
    for reference in references:
        key = (reference.source_section, reference.source_excerpt)
        if key in seen:
            continue
        seen.add(key)
        payload.append(
            {
                "source_section": reference.source_section[:120],
                "source_excerpt": reference.source_excerpt[:240],
            }
        )
        if len(payload) >= MAX_REFERENCES_PER_ITEM_FOR_GENERATION:
            break
    return payload


def _build_compatibility_analysis_text(
    candidate_payload: dict[str, Any],
    jobs_payload: list[dict[str, Any]],
    output_language: OutputLanguage | str,
) -> str:
    return "\n".join(
        [
            "<ASTROGATO_VECTOR_COMPATIBILITY_INPUT>",
            "",
            "<OUTPUT_LANGUAGE>",
            _language_value(output_language),
            "</OUTPUT_LANGUAGE>",
            "",
            "<CANDIDATE_EVIDENCE>",
            json.dumps(candidate_payload, ensure_ascii=False, indent=2),
            "</CANDIDATE_EVIDENCE>",
            "",
            "<JOB_ANALYSES>",
            json.dumps(jobs_payload, ensure_ascii=False, indent=2),
            "</JOB_ANALYSES>",
            "",
            "</ASTROGATO_VECTOR_COMPATIBILITY_INPUT>",
        ]
    )


def _reduce_payload_text(text: str, max_chars: int) -> str:
    head_chars = max(1_000, int(max_chars * 0.76))
    tail_chars = max(1_000, max_chars - head_chars)
    return "\n\n[... CONTENIDO INTERMEDIO OMITIDO POR LIMITE TECNICO ...]\n\n".join(
        [text[:head_chars].rstrip(), text[-tail_chars:].lstrip()]
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


def _format_audit_findings(findings: list[object]) -> list[str]:
    return [f"{finding.severity}: {finding.path}: {finding.message}" for finding in findings]


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _language_value(value: OutputLanguage | str) -> str:
    return str(getattr(value, "value", value))


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))
