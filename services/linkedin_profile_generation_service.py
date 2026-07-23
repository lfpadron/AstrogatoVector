"""LinkedIn profile generation with evidence and market separation."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from schemas.enums import OutputLanguage, PriorityLevel
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EvidenceItem,
    EvidenceReference,
)
from schemas.market_models import JobRequirement, TargetMarketAnalysis
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from schemas.profile_models import LinkedInProfileOutput
from services.linkedin_profile_audit_service import audit_linkedin_profile_output
from services.openai_service import OpenAIService
from services.prompt_loader import PromptLoadError, load_prompt
from utils.constants import (
    MAX_MARKET_KEYWORDS_FOR_GENERATION,
    MAX_PROFILE_EXPERIENCE_ENTRIES,
    MAX_PROFILE_GENERATION_INPUT_CHARS,
    MAX_REFERENCES_PER_ITEM_FOR_GENERATION,
)

PromptLoader = Callable[[str], str]
StatusCallback = Callable[[str], None]

LINKEDIN_PROFILE_PROMPT_VERSION = "1.0"
PROFILE_GENERATION_TRUNCATION_WARNING = (
    "La evidencia resumida para generar el perfil superó el tamaño recomendado. "
    "Se usó una versión reducida y el resultado requiere revisión adicional."
)
PROFILE_EXPERIENCE_TRUNCATION_WARNING = (
    "El perfil contiene más empleos de los recomendados para esta etapa. "
    "Se conservaron los empleos más recientes para la generación."
)
PROFILE_AUDIT_REJECTION_MESSAGE = (
    "La propuesta fue recibida, pero no superó la validación de evidencia. "
    "No se utilizará porque contiene afirmaciones, tecnologías, cifras o responsabilidades "
    "que no pudieron respaldarse con la trayectoria profesional."
)
PROFILE_INVALID_STRUCTURE_MESSAGE = (
    "El modelo no devolvió una propuesta de perfil de LinkedIn válida. No se generaron resultados parciales."
)


@dataclass(frozen=True)
class LinkedInProfileGenerationPayload:
    """Prepared payload for LinkedIn profile generation."""

    user_input: str
    warnings: list[str]


class LinkedInProfileGenerationService:
    """Generate LinkedIn profile text from audited candidate and market outputs."""

    def __init__(
        self,
        openai_service: OpenAIService,
        *,
        prompt_loader: PromptLoader = load_prompt,
    ) -> None:
        self.openai_service = openai_service
        self._prompt_loader = prompt_loader

    def generate_profile(
        self,
        candidate_profile: CandidateProfessionalProfile,
        market_analysis: TargetMarketAnalysis,
        output_language: OutputLanguage | str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> LinkedInProfileGenerationResult:
        """Run structured LinkedIn profile generation."""
        start_time = time.perf_counter()
        warnings: list[str] = []

        try:
            if status_callback:
                status_callback("Preparando la estrategia de posicionamiento...")
            system_prompt = self._prompt_loader("system_guardrails.txt")
            generation_prompt = self._prompt_loader("generate_profile.txt")
            payload = prepare_linkedin_profile_generation_payload(
                candidate_profile,
                market_analysis,
                output_language,
            )
            warnings.extend(payload.warnings)

            if status_callback:
                status_callback("Generando el headline y el Acerca de...")
            result = self.openai_service.parse_structured_response(
                model_name=self.openai_service.settings.model_quality,
                system_prompt=system_prompt,
                user_prompt=f"{generation_prompt}\n\n{payload.user_input}",
                response_model=LinkedInProfileOutput,
            )
        except PromptLoadError:
            return LinkedInProfileGenerationResult(
                success=False,
                model_used=self.openai_service.settings.model_quality,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de generación del perfil de LinkedIn.",
                retryable=False,
                prompt_version=LINKEDIN_PROFILE_PROMPT_VERSION,
            )

        latency_ms = _elapsed_ms(start_time)
        if not result.success or result.parsed is None:
            return LinkedInProfileGenerationResult(
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
                user_message=result.error_message or PROFILE_INVALID_STRUCTURE_MESSAGE,
                retryable=result.retryable,
                prompt_version=LINKEDIN_PROFILE_PROMPT_VERSION,
            )

        if status_callback:
            status_callback("Reescribiendo la experiencia profesional...")
        if status_callback:
            status_callback("Priorizando skills y palabras clave...")
        if status_callback:
            status_callback("Validando que no existan afirmaciones no respaldadas...")
        audit = audit_linkedin_profile_output(result.parsed, candidate_profile, market_analysis)
        audit_findings = _format_audit_findings(audit.findings)
        warnings.extend(finding for finding in audit_findings if finding.startswith("warning:"))

        if not audit.passed:
            return LinkedInProfileGenerationResult(
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
                error_category="linkedin_profile_audit_failed",
                user_message=PROFILE_AUDIT_REJECTION_MESSAGE,
                retryable=False,
                prompt_version=LINKEDIN_PROFILE_PROMPT_VERSION,
            )

        return LinkedInProfileGenerationResult(
            success=True,
            profile_output=result.parsed,
            model_used=result.model or self.openai_service.settings.model_quality,
            request_id=result.request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            audit_passed=True,
            audit_findings=audit_findings,
            warnings=_unique_preserving_order(warnings),
            prompt_version=LINKEDIN_PROFILE_PROMPT_VERSION,
        )


def prepare_linkedin_profile_generation_payload(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
) -> LinkedInProfileGenerationPayload:
    """Build the reduced delimited profile-generation payload."""
    warnings: list[str] = []
    candidate_payload = _candidate_payload(candidate_profile, warnings)
    market_payload = _market_payload(market_analysis)
    user_input = _build_profile_generation_text(candidate_payload, market_payload, output_language)
    if len(user_input) > MAX_PROFILE_GENERATION_INPUT_CHARS:
        warnings.append(PROFILE_GENERATION_TRUNCATION_WARNING)
        market_payload["keywords"] = market_payload.get("keywords", [])[:50]
        market_payload["job_analyses"] = market_payload.get("job_analyses", [])[:6]
        user_input = _build_profile_generation_text(candidate_payload, market_payload, output_language)
    if len(user_input) > MAX_PROFILE_GENERATION_INPUT_CHARS:
        user_input = _reduce_payload_text(user_input, MAX_PROFILE_GENERATION_INPUT_CHARS)
    return LinkedInProfileGenerationPayload(
        user_input=user_input,
        warnings=_unique_preserving_order(warnings),
    )


def build_linkedin_profile_generation_input(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
) -> str:
    """Return the safe, delimited user message for LinkedIn profile generation."""
    return prepare_linkedin_profile_generation_payload(candidate_profile, market_analysis, output_language).user_input


def build_linkedin_profile_generation_fingerprint(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
    *,
    model_name: str,
    prompt_version: str = LINKEDIN_PROFILE_PROMPT_VERSION,
) -> str:
    """Build a local fingerprint from reduced candidate and market data."""
    payload = prepare_linkedin_profile_generation_payload(candidate_profile, market_analysis, output_language)
    hasher = hashlib.sha256()
    for value in (_language_value(output_language), model_name, prompt_version, payload.user_input):
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _candidate_payload(candidate_profile: CandidateProfessionalProfile, warnings: list[str]) -> dict[str, Any]:
    employment_history = candidate_profile.employment_history[:MAX_PROFILE_EXPERIENCE_ENTRIES]
    if len(candidate_profile.employment_history) > MAX_PROFILE_EXPERIENCE_ENTRIES:
        warnings.append(PROFILE_EXPERIENCE_TRUNCATION_WARNING)
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
                "location": employment.location,
                "responsibilities": [_evidence_item_payload(item) for item in employment.responsibilities],
                "achievements": [_achievement_payload(achievement) for achievement in employment.achievements],
                "technologies": [_skill_payload(skill) for skill in employment.technologies],
                "industries": employment.industries,
            }
            for employment in employment_history
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


def _market_payload(market_analysis: TargetMarketAnalysis) -> dict[str, Any]:
    keywords = sorted(
        market_analysis.keywords,
        key=lambda keyword: (_priority_order(keyword.priority), -keyword.frequency, keyword.normalized_keyword),
    )[:MAX_MARKET_KEYWORDS_FOR_GENERATION]
    return {
        "target_role_family": market_analysis.target_role_family,
        "suggested_target_titles": market_analysis.suggested_target_titles,
        "dominant_seniority": _enum_value(market_analysis.dominant_seniority),
        "market_summary": market_analysis.market_summary,
        "common_responsibilities": market_analysis.common_responsibilities,
        "common_requirements": [_requirement_payload(requirement) for requirement in market_analysis.common_requirements],
        "keywords": [
            {
                "keyword": keyword.keyword,
                "normalized_keyword": keyword.normalized_keyword,
                "frequency": keyword.frequency,
                "job_indices": keyword.job_indices,
                "category": _enum_value(keyword.category),
                "priority": _enum_value(keyword.priority),
            }
            for keyword in keywords
        ],
        "technical_skills": market_analysis.technical_skills,
        "leadership_skills": market_analysis.leadership_skills,
        "business_skills": market_analysis.business_skills,
        "tools_and_technologies": market_analysis.tools_and_technologies,
        "industries": market_analysis.industries,
        "differentiators": market_analysis.differentiators,
        "job_analyses": [
            {
                "job_index": job.job_index,
                "title": job.title,
                "company": job.company,
                "inferred_seniority": _enum_value(job.inferred_seniority),
                "distinctive_requirements": [_requirement_payload(requirement) for requirement in job.requirements[:8]],
                "tools_and_technologies": job.tools_and_technologies,
                "exact_keywords": job.exact_keywords,
            }
            for job in market_analysis.job_analyses
        ],
    }


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


def _build_profile_generation_text(
    candidate_payload: dict[str, Any],
    market_payload: dict[str, Any],
    output_language: OutputLanguage | str,
) -> str:
    return "\n".join(
        [
            "<ASTROGATO_VECTOR_PROFILE_GENERATION>",
            "",
            "<OUTPUT_LANGUAGE>",
            _language_value(output_language),
            "</OUTPUT_LANGUAGE>",
            "",
            "<CANDIDATE_EVIDENCE>",
            json.dumps(candidate_payload, ensure_ascii=False, indent=2),
            "</CANDIDATE_EVIDENCE>",
            "",
            "<TARGET_MARKET>",
            json.dumps(market_payload, ensure_ascii=False, indent=2),
            "</TARGET_MARKET>",
            "",
            "</ASTROGATO_VECTOR_PROFILE_GENERATION>",
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
