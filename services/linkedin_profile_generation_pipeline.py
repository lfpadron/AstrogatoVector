"""Orchestration for LinkedIn profile generation with session reuse support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from services.linkedin_profile_generation_service import (
    LINKEDIN_PROFILE_PROMPT_VERSION,
    LinkedInProfileGenerationService,
    build_linkedin_profile_generation_fingerprint,
)
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service

StatusCallback = Callable[[str], None]
OpenAIServiceFactory = Callable[[], OpenAIService]

SESSION_REUSE_MESSAGE = (
    "Se reutilizó el perfil generado durante esta sesión porque la evidencia y las vacantes no cambiaron."
)


@dataclass(frozen=True)
class LinkedInProfileGenerationRun:
    """Pipeline result plus fingerprint metadata."""

    result: LinkedInProfileGenerationResult
    fingerprint: str | None
    reused: bool


def run_linkedin_profile_generation_pipeline(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    output_language: OutputLanguage | str,
    *,
    existing_result: LinkedInProfileGenerationResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: OpenAIServiceFactory | None = None,
    status_callback: StatusCallback | None = None,
) -> LinkedInProfileGenerationRun:
    """Generate or reuse a LinkedIn profile output for the current inputs."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service = factory()
    except OpenAIConfigurationError as exc:
        return LinkedInProfileGenerationRun(
            result=LinkedInProfileGenerationResult(
                success=False,
                error_category="configuration_error",
                user_message="La configuración de OpenAI está incompleta: " + " ".join(exc.errors),
                retryable=False,
                prompt_version=LINKEDIN_PROFILE_PROMPT_VERSION,
            ),
            fingerprint=None,
            reused=False,
        )

    fingerprint = build_linkedin_profile_generation_fingerprint(
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
        and existing_result.profile_output is not None
    ):
        reused_result = existing_result.model_copy(
            update={
                "reused_from_session": True,
                "warnings": [*existing_result.warnings, SESSION_REUSE_MESSAGE],
            }
        )
        return LinkedInProfileGenerationRun(result=reused_result, fingerprint=fingerprint, reused=True)

    service = LinkedInProfileGenerationService(openai_service)
    result = service.generate_profile(
        candidate_profile,
        market_analysis,
        output_language,
        status_callback=status_callback,
    )
    return LinkedInProfileGenerationRun(result=result, fingerprint=fingerprint, reused=False)
