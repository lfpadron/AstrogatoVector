"""Target jobs analysis orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.enums import OutputLanguage
from schemas.input_models import JobInput
from schemas.job_analysis_models import JobAnalysisResult
from services.job_analysis_service import JobAnalysisService, build_jobs_analysis_fingerprint
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service

CONFIGURATION_BLOCKED_MESSAGE = (
    "La información de entrada fue preparada correctamente, pero no se puede realizar el análisis de vacantes "
    "porque la configuración de OpenAI está incompleta."
)
SESSION_REUSE_MESSAGE = "Se reutilizó el análisis de vacantes de esta sesión porque las descripciones no cambiaron."


@dataclass(frozen=True)
class JobAnalysisRun:
    """Result of one target jobs analysis orchestration attempt."""

    result: JobAnalysisResult
    fingerprint: str | None = None
    reused: bool = False


def run_job_analysis_pipeline(
    jobs: list[JobInput],
    output_language: OutputLanguage | str,
    *,
    existing_result: JobAnalysisResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: Callable[[], OpenAIService] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> JobAnalysisRun:
    """Run or reuse target market analysis for the provided job inputs."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service = factory()
    except OpenAIConfigurationError as exc:
        return JobAnalysisRun(
            result=JobAnalysisResult(
                success=False,
                audit_passed=False,
                error_category="configuration_error",
                user_message=CONFIGURATION_BLOCKED_MESSAGE,
                warnings=list(exc.errors),
                retryable=False,
            )
        )

    fingerprint = build_jobs_analysis_fingerprint(
        jobs,
        output_language,
        model_name=openai_service.settings.model_quality,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.market_analysis is not None
    ):
        return JobAnalysisRun(
            result=existing_result.model_copy(
                update={
                    "reused_from_session": True,
                    "warnings": [*existing_result.warnings, SESSION_REUSE_MESSAGE],
                }
            ),
            fingerprint=fingerprint,
            reused=True,
        )

    service = JobAnalysisService(openai_service)
    return JobAnalysisRun(
        result=service.analyze_jobs(jobs, output_language, status_callback=status_callback),
        fingerprint=fingerprint,
        reused=False,
    )
