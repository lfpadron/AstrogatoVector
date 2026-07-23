"""Application communication generation orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.application_communication_models import (
    APPLICATION_COMMUNICATION_PROMPT_VERSION,
    ApplicationCommunicationAuditResult,
    ApplicationCommunicationGenerationResult,
    CommunicationRedundancyAuditResult,
)
from schemas.compatibility_models import JobCompatibility
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import TargetedCV
from services.application_communication_audit_service import audit_application_communication_kit
from services.application_communication_service import (
    ApplicationCommunicationService,
    build_application_communication_input_fingerprint,
)
from services.communication_redundancy_audit_service import audit_communication_redundancy
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service

StatusCallback = Callable[[str], None]
OpenAIServiceFactory = Callable[[], OpenAIService]

APPLICATION_COMMUNICATION_CONFIGURATION_MESSAGE = (
    "El perfil profesional, la vacante, la compatibilidad y el CV específico están preparados, "
    "pero no se puede generar la comunicación porque la configuración de OpenAI está incompleta."
)
APPLICATION_COMMUNICATION_SESSION_REUSE_MESSAGE = (
    "Se reutilizó el kit de comunicación porque la evidencia, la vacante, la compatibilidad y el CV específico no cambiaron."
)
APPLICATION_COMMUNICATION_MISSING_TARGETED_CV_MESSAGE = (
    "Para generar la comunicación de esta vacante, primero debes generar y validar su CV específico."
)


@dataclass(frozen=True)
class ApplicationCommunicationGenerationRun:
    """Pipeline result plus fingerprint and local audits."""

    result: ApplicationCommunicationGenerationResult
    fingerprint: str | None = None
    audit: ApplicationCommunicationAuditResult | None = None
    redundancy_audit: CommunicationRedundancyAuditResult | None = None
    reused: bool = False


def run_application_communication_generation_pipeline(
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    output_language: OutputLanguage | str,
    *,
    existing_result: ApplicationCommunicationGenerationResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: OpenAIServiceFactory | None = None,
    status_callback: StatusCallback | None = None,
) -> ApplicationCommunicationGenerationRun:
    """Generate or reuse a communication kit for one job."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service = factory()
    except OpenAIConfigurationError as exc:
        return ApplicationCommunicationGenerationRun(
            result=ApplicationCommunicationGenerationResult(
                success=False,
                audit_passed=False,
                redundancy_audit_passed=False,
                error_category="configuration_error",
                user_message=APPLICATION_COMMUNICATION_CONFIGURATION_MESSAGE,
                warnings=list(exc.errors),
                retryable=False,
                prompt_version=APPLICATION_COMMUNICATION_PROMPT_VERSION,
            ),
            fingerprint=None,
            reused=False,
        )

    fingerprint = build_application_communication_input_fingerprint(
        candidate_profile,
        job_analysis,
        job_compatibility,
        targeted_cv,
        output_language,
        model_name=openai_service.settings.model_quality,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.communication_kit is not None
    ):
        audit = audit_application_communication_kit(
            existing_result.communication_kit,
            candidate_profile,
            job_analysis,
            job_compatibility,
            targeted_cv,
        )
        redundancy = audit_communication_redundancy(existing_result.communication_kit, targeted_cv)
        reused_result = existing_result.model_copy(
            update={
                "reused_from_session": True,
                "warnings": [*existing_result.warnings, APPLICATION_COMMUNICATION_SESSION_REUSE_MESSAGE],
                "audit_passed": audit.passed,
                "redundancy_audit_passed": redundancy.passed,
            }
        )
        return ApplicationCommunicationGenerationRun(
            result=reused_result,
            fingerprint=fingerprint,
            audit=audit,
            redundancy_audit=redundancy,
            reused=True,
        )

    service = ApplicationCommunicationService(openai_service)
    result = service.generate_communication_kit(
        candidate_profile,
        job_analysis,
        job_compatibility,
        targeted_cv,
        output_language,
        status_callback=status_callback,
    )
    audit = None
    redundancy = None
    if result.success and result.communication_kit is not None:
        audit = audit_application_communication_kit(
            result.communication_kit,
            candidate_profile,
            job_analysis,
            job_compatibility,
            targeted_cv,
        )
        redundancy = audit_communication_redundancy(result.communication_kit, targeted_cv)
    return ApplicationCommunicationGenerationRun(
        result=result,
        fingerprint=fingerprint,
        audit=audit,
        redundancy_audit=redundancy,
        reused=False,
    )
