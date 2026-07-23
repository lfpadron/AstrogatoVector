"""Compatibility analysis orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from schemas.compatibility_models import COMPATIBILITY_METHODOLOGY_VERSION
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from services.compatibility_service import (
    COMPATIBILITY_PROMPT_VERSION,
    CompatibilityService,
    build_compatibility_analysis_fingerprint,
)
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service

CONFIGURATION_BLOCKED_MESSAGE = (
    "El perfil profesional y el mercado objetivo están preparados, pero no se puede calcular compatibilidad "
    "porque la configuración de OpenAI está incompleta."
)
SESSION_REUSE_MESSAGE = (
    "Se reutilizó el análisis de compatibilidad porque la evidencia, las vacantes y la metodología no cambiaron."
)


@dataclass(frozen=True)
class CompatibilityAnalysisRun:
    """Result of one compatibility analysis orchestration attempt."""

    result: CompatibilityAnalysisResult
    fingerprint: str | None = None
    reused: bool = False


def run_compatibility_pipeline(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
    *,
    existing_result: CompatibilityAnalysisResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: Callable[[], OpenAIService] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> CompatibilityAnalysisRun:
    """Run or reuse compatibility analysis for current candidate and market."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service = factory()
    except OpenAIConfigurationError as exc:
        return CompatibilityAnalysisRun(
            result=CompatibilityAnalysisResult(
                success=False,
                audit_passed=False,
                error_category="configuration_error",
                user_message=CONFIGURATION_BLOCKED_MESSAGE,
                warnings=list(exc.errors),
                retryable=False,
                prompt_version=COMPATIBILITY_PROMPT_VERSION,
                methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            )
        )

    fingerprint = build_compatibility_analysis_fingerprint(
        candidate_profile,
        market_analysis,
        output_language,
        model_name=openai_service.settings.model_quality,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.compatibility_report is not None
        and existing_result.semantic_evaluation is not None
    ):
        return CompatibilityAnalysisRun(
            result=existing_result.model_copy(
                update={
                    "reused_from_session": True,
                    "warnings": [*existing_result.warnings, SESSION_REUSE_MESSAGE],
                }
            ),
            fingerprint=fingerprint,
            reused=True,
        )

    service = CompatibilityService(openai_service)
    return CompatibilityAnalysisRun(
        result=service.analyze_compatibility(
            candidate_profile,
            market_analysis,
            output_language,
            status_callback=status_callback,
        ),
        fingerprint=fingerprint,
        reused=False,
    )
