"""Targeted CV generation orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.compatibility_models import JobCompatibility
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import (
    TARGETED_CV_PROMPT_VERSION,
    TargetedCVATSAudit,
    TargetedCVGenerationResult,
)
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service
from services.targeted_cv_ats_audit_service import audit_targeted_cv_ats
from services.targeted_cv_generation_service import (
    TargetedCVGenerationService,
    build_targeted_cv_input_fingerprint,
)

StatusCallback = Callable[[str], None]
OpenAIServiceFactory = Callable[[], OpenAIService]

TARGETED_CV_CONFIGURATION_MESSAGE = (
    "El perfil profesional, la vacante y la compatibilidad están preparados, pero no se puede generar "
    "el CV específico porque la configuración de OpenAI está incompleta."
)
TARGETED_CV_SESSION_REUSE_MESSAGE = (
    "Se reutilizó el CV específico porque la evidencia, la vacante y la compatibilidad no cambiaron."
)


@dataclass(frozen=True)
class TargetedCVGenerationRun:
    """Pipeline result plus fingerprint and local ATS audit."""

    result: TargetedCVGenerationResult
    fingerprint: str | None = None
    ats_audit: TargetedCVATSAudit | None = None
    reused: bool = False


def run_targeted_cv_generation_pipeline(
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    output_language: OutputLanguage | str,
    *,
    existing_result: TargetedCVGenerationResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: OpenAIServiceFactory | None = None,
    status_callback: StatusCallback | None = None,
) -> TargetedCVGenerationRun:
    """Generate or reuse a targeted CV for one job."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service = factory()
    except OpenAIConfigurationError as exc:
        return TargetedCVGenerationRun(
            result=TargetedCVGenerationResult(
                success=False,
                audit_passed=False,
                error_category="configuration_error",
                user_message=TARGETED_CV_CONFIGURATION_MESSAGE,
                warnings=list(exc.errors),
                retryable=False,
                prompt_version=TARGETED_CV_PROMPT_VERSION,
            ),
            fingerprint=None,
            reused=False,
        )

    fingerprint = build_targeted_cv_input_fingerprint(
        candidate_profile,
        job_analysis,
        job_compatibility,
        output_language,
        model_name=openai_service.settings.model_quality,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.targeted_cv is not None
    ):
        ats_audit = audit_targeted_cv_ats(
            existing_result.targeted_cv,
            candidate_profile,
            job_analysis,
            job_compatibility,
        )
        reused_result = existing_result.model_copy(
            update={
                "reused_from_session": True,
                "warnings": [*existing_result.warnings, TARGETED_CV_SESSION_REUSE_MESSAGE],
            }
        )
        return TargetedCVGenerationRun(
            result=reused_result,
            fingerprint=fingerprint,
            ats_audit=ats_audit,
            reused=True,
        )

    service = TargetedCVGenerationService(openai_service)
    result = service.generate_targeted_cv(
        candidate_profile,
        job_analysis,
        job_compatibility,
        output_language,
        status_callback=status_callback,
    )
    ats_audit = None
    if result.success and result.targeted_cv is not None:
        ats_audit = audit_targeted_cv_ats(result.targeted_cv, candidate_profile, job_analysis, job_compatibility)
    return TargetedCVGenerationRun(result=result, fingerprint=fingerprint, ats_audit=ats_audit, reused=False)
