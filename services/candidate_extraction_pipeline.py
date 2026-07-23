"""Candidate extraction orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.extraction_models import CandidateExtractionResult
from schemas.input_models import CandidateInput
from services.candidate_extraction_service import (
    CandidateExtractionService,
    build_candidate_extraction_fingerprint,
)
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service

CONFIGURATION_BLOCKED_MESSAGE = (
    "La información de entrada fue preparada correctamente, pero no se puede realizar el análisis "
    "porque la configuración de OpenAI está incompleta."
)
SESSION_REUSE_MESSAGE = "Se reutilizó el análisis de esta sesión porque las fuentes no cambiaron."


@dataclass(frozen=True)
class CandidateExtractionRun:
    """Result of one extraction orchestration attempt."""

    result: CandidateExtractionResult
    fingerprint: str | None = None
    reused: bool = False


def run_candidate_extraction_pipeline(
    candidate_input: CandidateInput,
    *,
    existing_result: CandidateExtractionResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: Callable[[], OpenAIService] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> CandidateExtractionRun:
    """Run or reuse candidate extraction for the provided input."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service: OpenAIService = factory()
    except OpenAIConfigurationError as exc:
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=False,
                evidence_audit_passed=False,
                error_category="configuration_error",
                user_message=CONFIGURATION_BLOCKED_MESSAGE,
                warnings=list(exc.errors),
                retryable=False,
            )
        )

    fingerprint = build_candidate_extraction_fingerprint(
        candidate_input,
        model_name=openai_service.settings.model_quality,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.profile is not None
    ):
        return CandidateExtractionRun(
            result=existing_result.model_copy(
                update={
                    "reused_from_session": True,
                    "warnings": [*existing_result.warnings, SESSION_REUSE_MESSAGE],
                }
            ),
            fingerprint=fingerprint,
            reused=True,
        )

    service = CandidateExtractionService(openai_service)
    return CandidateExtractionRun(
        result=service.extract_candidate_profile(candidate_input, status_callback=status_callback),
        fingerprint=fingerprint,
        reused=False,
    )
