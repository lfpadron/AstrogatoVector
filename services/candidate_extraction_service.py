"""Candidate professional profile extraction with evidence controls."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass

from schemas.evidence_models import CandidateProfessionalProfile
from schemas.extraction_models import CandidateExtractionResult
from schemas.input_models import CandidateInput
from services.evidence_audit_service import audit_candidate_profile_evidence
from services.openai_service import OpenAIService
from services.privacy_filter import redact_sensitive_patterns
from services.prompt_loader import PromptLoadError, load_prompt
from utils.constants import (
    MAX_CANDIDATE_SOURCE_CHARS,
    MAX_CV_SOURCE_CHARS,
    MAX_LINKEDIN_SOURCE_CHARS,
)

PromptLoader = Callable[[str], str]
StatusCallback = Callable[[str], None]

CANDIDATE_EXTRACTION_PROMPT_VERSION = "candidate-extraction-v1"
CV_TRUNCATION_WARNING = (
    "El CV supera el tamaño recomendado. Se procesará una versión reducida y el resultado "
    "requerirá una revisión adicional."
)
LINKEDIN_TRUNCATION_WARNING = (
    "El perfil de LinkedIn supera el tamaño recomendado. Se procesará una versión reducida."
)
PRIVACY_REDACTION_WARNING = (
    "Se detectaron y redactaron patrones evidentes de datos sensibles antes del análisis."
)
EVIDENCE_REJECTION_MESSAGE = (
    "La respuesta fue recibida, pero no superó la validación de evidencia. "
    "No se utilizará este resultado porque contiene afirmaciones o referencias que no pudieron "
    "comprobarse en las fuentes. Puedes intentar reprocesarlo."
)
INVALID_STRUCTURE_MESSAGE = "El modelo no devolvió una estructura profesional válida. No se generaron resultados parciales."


@dataclass(frozen=True)
class CandidateExtractionPayload:
    """Prepared user payload for candidate extraction."""

    user_input: str
    source_text: str
    warnings: list[str]
    redaction_count: int
    redaction_categories: list[str]


class CandidateExtractionService:
    """Extract a structured profile using the encapsulated OpenAI service."""

    def __init__(
        self,
        openai_service: OpenAIService,
        *,
        prompt_loader: PromptLoader = load_prompt,
    ) -> None:
        self.openai_service = openai_service
        self._prompt_loader = prompt_loader

    def extract_candidate_profile(
        self,
        candidate_input: CandidateInput,
        *,
        status_callback: StatusCallback | None = None,
    ) -> CandidateExtractionResult:
        """Run candidate extraction and deterministic evidence audit."""
        start_time = time.perf_counter()
        warnings: list[str] = []

        try:
            if status_callback:
                status_callback("Preparando información profesional...")
            system_prompt = self._prompt_loader("system_guardrails.txt")
            extraction_prompt = self._prompt_loader("extract_candidate.txt")

            if status_callback:
                status_callback("Protegiendo datos sensibles...")
            payload = prepare_candidate_extraction_payload(candidate_input)
            warnings.extend(payload.warnings)

            if status_callback:
                status_callback("Analizando el CV y el perfil...")
            result = self.openai_service.parse_structured_response(
                model_name=self.openai_service.settings.model_quality,
                system_prompt=system_prompt,
                user_prompt=f"{extraction_prompt}\n\n{payload.user_input}",
                response_model=CandidateProfessionalProfile,
            )
        except PromptLoadError:
            return CandidateExtractionResult(
                success=False,
                model_used=self.openai_service.settings.model_quality,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de extracción profesional.",
                retryable=False,
            )

        latency_ms = _elapsed_ms(start_time)
        if not result.success or result.parsed is None:
            return CandidateExtractionResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                evidence_audit_passed=False,
                warnings=_unique_preserving_order([*warnings, *result.warnings]),
                error_category=result.error_code,
                user_message=result.error_message or INVALID_STRUCTURE_MESSAGE,
                retryable=result.retryable,
            )

        if status_callback:
            status_callback("Validando la evidencia...")
        audit = audit_candidate_profile_evidence(result.parsed, payload.source_text)
        audit_findings = _format_audit_findings(audit.findings)
        warnings.extend(finding for finding in audit_findings if finding.startswith("warning:"))

        if not audit.passed:
            return CandidateExtractionResult(
                success=False,
                model_used=result.model or self.openai_service.settings.model_quality,
                request_id=result.request_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                latency_ms=latency_ms,
                evidence_audit_passed=False,
                evidence_audit_findings=audit_findings,
                warnings=warnings,
                error_category="evidence_audit_failed",
                user_message=EVIDENCE_REJECTION_MESSAGE,
                retryable=False,
            )

        if status_callback:
            status_callback("Preparando el resultado...")
        return CandidateExtractionResult(
            success=True,
            profile=result.parsed,
            model_used=result.model or self.openai_service.settings.model_quality,
            request_id=result.request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            evidence_audit_passed=True,
            evidence_audit_findings=audit_findings,
            warnings=warnings,
        )


def prepare_candidate_extraction_payload(candidate_input: CandidateInput) -> CandidateExtractionPayload:
    """Build the delimited source payload after redaction and size control."""
    warnings: list[str] = []

    cv_privacy = redact_sensitive_patterns(_normalize_source_text(candidate_input.cv_text))
    linkedin_source = candidate_input.linkedin_text or "No se proporcionó perfil de LinkedIn."
    linkedin_privacy = redact_sensitive_patterns(_normalize_source_text(linkedin_source))

    if cv_privacy.redaction_count or linkedin_privacy.redaction_count:
        warnings.append(PRIVACY_REDACTION_WARNING)

    cv_text = _reduce_source_text(
        cv_privacy.filtered_text,
        max_chars=MAX_CV_SOURCE_CHARS,
        head_chars=50_000,
        tail_chars=15_000,
        truncation_warning=CV_TRUNCATION_WARNING,
        warnings=warnings,
    )
    linkedin_limit = min(MAX_LINKEDIN_SOURCE_CHARS, max(2_000, MAX_CANDIDATE_SOURCE_CHARS - len(cv_text)))
    linkedin_text = _reduce_source_text(
        linkedin_privacy.filtered_text,
        max_chars=linkedin_limit,
        head_chars=max(1_500, int(linkedin_limit * 0.75)),
        tail_chars=max(500, linkedin_limit - max(1_500, int(linkedin_limit * 0.75))),
        truncation_warning=LINKEDIN_TRUNCATION_WARNING,
        warnings=warnings,
    )

    linkedin_status = "provided" if candidate_input.linkedin_text else "not_provided"
    user_input = "\n".join(
        [
            "<ASTROGATO_VECTOR_INPUT>",
            "",
            "<OUTPUT_LANGUAGE>",
            _language_value(candidate_input.output_language),
            "</OUTPUT_LANGUAGE>",
            "",
            "<CV>",
            cv_text,
            "</CV>",
            "",
            f'<LINKEDIN_PROFILE status="{linkedin_status}">',
            linkedin_text,
            "</LINKEDIN_PROFILE>",
            "",
            "</ASTROGATO_VECTOR_INPUT>",
        ]
    )

    return CandidateExtractionPayload(
        user_input=user_input,
        source_text=user_input,
        warnings=_unique_preserving_order(warnings),
        redaction_count=cv_privacy.redaction_count + linkedin_privacy.redaction_count,
        redaction_categories=_unique_preserving_order(
            [*cv_privacy.detected_categories, *linkedin_privacy.detected_categories]
        ),
    )


def build_candidate_extraction_input(candidate_input: CandidateInput) -> str:
    """Return the safe, delimited user message for candidate extraction."""
    return prepare_candidate_extraction_payload(candidate_input).user_input


def build_candidate_extraction_fingerprint(
    candidate_input: CandidateInput,
    *,
    model_name: str,
    prompt_version: str = CANDIDATE_EXTRACTION_PROMPT_VERSION,
) -> str:
    """Build a local fingerprint to avoid duplicate extraction calls in one session."""
    hasher = hashlib.sha256()
    for value in (
        candidate_input.cv_text,
        candidate_input.linkedin_text or "",
        _language_value(candidate_input.output_language),
        prompt_version,
        model_name,
    ):
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _normalize_source_text(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized_lines: list[str] = []
    previous: str | None = None
    blank_seen = False
    for line in lines:
        stripped = " ".join(line.strip().split())
        if not stripped:
            if not blank_seen and normalized_lines:
                normalized_lines.append("")
            blank_seen = True
            previous = None
            continue
        blank_seen = False
        if stripped == previous:
            continue
        normalized_lines.append(stripped)
        previous = stripped
    return "\n".join(normalized_lines).strip()


def _language_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _reduce_source_text(
    text: str,
    *,
    max_chars: int,
    head_chars: int,
    tail_chars: int,
    truncation_warning: str,
    warnings: list[str],
) -> str:
    if len(text) <= max_chars:
        return text

    warnings.append(truncation_warning)
    head = _clip_without_cutting_word(text, head_chars)
    tail = _clip_without_cutting_word_from_end(text, tail_chars)
    return "\n\n[... CONTENIDO INTERMEDIO OMITIDO POR LÍMITE TÉCNICO ...]\n\n".join([head, tail])


def _clip_without_cutting_word(text: str, limit: int) -> str:
    clipped = text[:limit]
    if len(clipped) == len(text) or clipped.endswith((" ", "\n", "\t")):
        return clipped.strip()
    return (clipped.rsplit(" ", 1)[0] or clipped).strip()


def _clip_without_cutting_word_from_end(text: str, limit: int) -> str:
    clipped = text[-limit:]
    if clipped.startswith((" ", "\n", "\t")):
        return clipped.strip()
    return (clipped.split(" ", 1)[1] if " " in clipped else clipped).strip()


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


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))
