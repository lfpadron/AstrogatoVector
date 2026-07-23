"""Target jobs analysis with strict source separation from candidate data."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass

from schemas.enums import OutputLanguage
from schemas.input_models import JobInput
from schemas.job_analysis_models import JobAnalysisResult
from schemas.market_models import TargetMarketAnalysis
from services.job_analysis_audit_service import audit_target_market_analysis
from services.openai_service import OpenAIService
from services.privacy_filter import redact_sensitive_patterns
from services.prompt_loader import PromptLoadError, load_prompt
from utils.constants import MAX_ALL_JOBS_SOURCE_CHARS, MAX_JOB_DESCRIPTION_CHARS

PromptLoader = Callable[[str], str]
StatusCallback = Callable[[str], None]

JOBS_ANALYSIS_PROMPT_VERSION = "1.0"
JOBS_TRUNCATION_WARNING = (
    "Una o más vacantes superan el tamaño recomendado. Se analizaron versiones reducidas y el resultado "
    "requiere revisión adicional."
)
JOBS_PRIVACY_WARNING = "Se detectaron y redactaron patrones evidentes de datos sensibles en vacantes."
AUDIT_REJECTION_MESSAGE = (
    "La respuesta fue recibida, pero no superó una validación crítica del análisis de vacantes. "
    "No se utilizará este resultado porque contiene inconsistencias estructurales, keywords o herramientas sin respaldo."
)
INVALID_STRUCTURE_MESSAGE = "El modelo no devolvió un análisis de mercado válido. No se generaron resultados parciales."


@dataclass(frozen=True)
class JobsAnalysisPayload:
    """Prepared payload for target jobs analysis."""

    user_input: str
    warnings: list[str]
    redaction_count: int


class JobAnalysisService:
    """Analyze target jobs using the encapsulated OpenAI service."""

    def __init__(
        self,
        openai_service: OpenAIService,
        *,
        prompt_loader: PromptLoader = load_prompt,
    ) -> None:
        self.openai_service = openai_service
        self._prompt_loader = prompt_loader

    def analyze_jobs(
        self,
        jobs: list[JobInput],
        output_language: OutputLanguage | str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> JobAnalysisResult:
        """Run structured target market analysis for job postings only."""
        start_time = time.perf_counter()
        warnings: list[str] = []

        try:
            if status_callback:
                status_callback("Preparando vacantes...")
            system_prompt = self._prompt_loader("system_guardrails.txt")
            analysis_prompt = self._prompt_loader("analyze_jobs.txt")

            payload = prepare_jobs_analysis_payload(jobs, output_language)
            warnings.extend(payload.warnings)

            if status_callback:
                status_callback("Analizando requisitos y responsabilidades...")
            result = self.openai_service.parse_structured_response(
                model_name=self.openai_service.settings.model_quality,
                system_prompt=system_prompt,
                user_prompt=f"{analysis_prompt}\n\n{payload.user_input}",
                response_model=TargetMarketAnalysis,
            )
        except PromptLoadError:
            return JobAnalysisResult(
                success=False,
                model_used=self.openai_service.settings.model_quality,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de análisis de vacantes.",
                retryable=False,
                prompt_version=JOBS_ANALYSIS_PROMPT_VERSION,
            )

        latency_ms = _elapsed_ms(start_time)
        if not result.success or result.parsed is None:
            return JobAnalysisResult(
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
                user_message=result.error_message or INVALID_STRUCTURE_MESSAGE,
                retryable=result.retryable,
                prompt_version=JOBS_ANALYSIS_PROMPT_VERSION,
            )

        if status_callback:
            status_callback("Consolidando palabras clave...")
        if status_callback:
            status_callback("Validando el análisis del mercado...")
        audit = audit_target_market_analysis(result.parsed, jobs)
        audit_findings = _format_audit_findings(audit.findings)
        warnings.extend(finding for finding in audit_findings if finding.startswith("warning:"))

        if not audit.passed:
            return JobAnalysisResult(
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
                error_category="job_analysis_audit_failed",
                user_message=AUDIT_REJECTION_MESSAGE,
                retryable=False,
                prompt_version=JOBS_ANALYSIS_PROMPT_VERSION,
            )

        return JobAnalysisResult(
            success=True,
            market_analysis=result.parsed,
            model_used=result.model or self.openai_service.settings.model_quality,
            request_id=result.request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            audit_passed=True,
            audit_findings=audit_findings,
            warnings=warnings,
            prompt_version=JOBS_ANALYSIS_PROMPT_VERSION,
        )


def prepare_jobs_analysis_payload(
    jobs: list[JobInput],
    output_language: OutputLanguage | str,
) -> JobsAnalysisPayload:
    """Build the delimited jobs-only payload after redaction and size control."""
    warnings: list[str] = []
    prepared_jobs: list[tuple[JobInput, str]] = []
    redaction_count = 0

    per_job_limit = min(MAX_JOB_DESCRIPTION_CHARS, max(1_000, MAX_ALL_JOBS_SOURCE_CHARS // max(1, len(jobs))))
    for job in jobs:
        normalized = _normalize_source_text(job.description)
        privacy_result = redact_sensitive_patterns(normalized)
        redaction_count += privacy_result.redaction_count
        description = _reduce_description(
            privacy_result.filtered_text,
            max_chars=per_job_limit,
            warnings=warnings,
        )
        prepared_jobs.append((job, description))

    if redaction_count:
        warnings.append(JOBS_PRIVACY_WARNING)

    user_input = _build_jobs_payload_text(prepared_jobs, output_language)
    return JobsAnalysisPayload(
        user_input=user_input,
        warnings=_unique_preserving_order(warnings),
        redaction_count=redaction_count,
    )


def build_jobs_analysis_input(
    jobs: list[JobInput],
    output_language: OutputLanguage | str,
) -> str:
    """Return the safe, delimited user message for target jobs analysis."""
    return prepare_jobs_analysis_payload(jobs, output_language).user_input


def build_jobs_analysis_fingerprint(
    jobs: list[JobInput],
    output_language: OutputLanguage | str,
    *,
    model_name: str,
    prompt_version: str = JOBS_ANALYSIS_PROMPT_VERSION,
) -> str:
    """Build a local fingerprint from job-only inputs and model metadata."""
    hasher = hashlib.sha256()
    for value in (_language_value(output_language), model_name, prompt_version):
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\0")
    for job in jobs:
        for value in (
            str(job.index),
            job.title,
            job.company or "",
            job.description,
            job.url or "",
            _source_value(job.source),
        ):
            hasher.update(value.encode("utf-8"))
            hasher.update(b"\0")
    return hasher.hexdigest()


def _build_jobs_payload_text(
    prepared_jobs: list[tuple[JobInput, str]],
    output_language: OutputLanguage | str,
) -> str:
    lines = [
        "<ASTROGATO_VECTOR_JOBS_INPUT>",
        "",
        "<OUTPUT_LANGUAGE>",
        _language_value(output_language),
        "</OUTPUT_LANGUAGE>",
        "",
    ]
    for job, description in prepared_jobs:
        lines.extend(
            [
                f'<JOB index="{job.index}">',
                f"<TITLE>{job.title}</TITLE>",
                f"<COMPANY>{job.company or 'No proporcionada'}</COMPANY>",
                f"<SOURCE>{_source_value(job.source)}</SOURCE>",
                f"<URL>{job.url or 'No proporcionada'}</URL>",
                "<DESCRIPTION>",
                description,
                "</DESCRIPTION>",
                "</JOB>",
                "",
            ]
        )
    lines.append("</ASTROGATO_VECTOR_JOBS_INPUT>")
    return "\n".join(lines)


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


def _reduce_description(text: str, *, max_chars: int, warnings: list[str]) -> str:
    if len(text) <= max_chars:
        return text
    warnings.append(JOBS_TRUNCATION_WARNING)
    head_chars = max(500, int(max_chars * 0.72))
    tail_chars = max(300, max_chars - head_chars)
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


def _language_value(value: OutputLanguage | str) -> str:
    return str(getattr(value, "value", value))


def _source_value(value: object) -> str:
    return str(getattr(value, "value", value))


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
