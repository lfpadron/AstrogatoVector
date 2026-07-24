"""Editorial plan generation orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.editorial_plan_models import (
    EDITORIAL_PLAN_PROMPT_VERSION,
    EditorialPlanAuditResult,
    EditorialPlanGenerationResult,
)
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from services.editorial_plan_audit_service import audit_editorial_plan
from services.editorial_plan_service import (
    EditorialPlanService,
    build_editorial_plan_input_fingerprint,
)
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService, create_openai_service

StatusCallback = Callable[[str], None]
OpenAIServiceFactory = Callable[[], OpenAIService]

EDITORIAL_PLAN_CONFIGURATION_MESSAGE = (
    "El perfil profesional, mercado, compatibilidad y auditoría están preparados, pero no se puede generar "
    "el plan editorial porque la configuración de OpenAI está incompleta."
)
EDITORIAL_PLAN_SESSION_REUSE_MESSAGE = (
    "Se reutilizó el plan editorial porque el perfil, mercado, compatibilidad y auditoría no cambiaron."
)
EDITORIAL_PLAN_MISSING_STAGES_MESSAGE = (
    "Para generar el plan editorial se necesita primero un perfil profesional válido, mercado objetivo, "
    "compatibilidad y auditoría integral válida."
)


@dataclass(frozen=True)
class EditorialPlanGenerationRun:
    """Pipeline result plus fingerprint and local audit."""

    result: EditorialPlanGenerationResult
    fingerprint: str | None = None
    audit: EditorialPlanAuditResult | None = None
    reused: bool = False


def run_editorial_plan_generation_pipeline(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
    output_language: OutputLanguage | str,
    *,
    existing_result: EditorialPlanGenerationResult | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    openai_service_factory: OpenAIServiceFactory | None = None,
    status_callback: StatusCallback | None = None,
) -> EditorialPlanGenerationRun:
    """Generate or reuse a four-week editorial plan."""
    factory = openai_service_factory or create_openai_service
    try:
        openai_service = factory()
    except OpenAIConfigurationError as exc:
        return EditorialPlanGenerationRun(
            result=EditorialPlanGenerationResult(
                success=False,
                audit_passed=False,
                error_category="configuration_error",
                user_message=EDITORIAL_PLAN_CONFIGURATION_MESSAGE,
                warnings=list(exc.errors),
                retryable=False,
                prompt_version=EDITORIAL_PLAN_PROMPT_VERSION,
            ),
            fingerprint=None,
            reused=False,
        )

    fingerprint = build_editorial_plan_input_fingerprint(
        candidate_profile,
        market_analysis,
        compatibility_report,
        audit_report,
        output_language,
        model_name=openai_service.settings.model_quality,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.professional_brand_plan is not None
    ):
        audit = audit_editorial_plan(
            existing_result.professional_brand_plan,
            candidate_profile,
            market_analysis,
            compatibility_report,
            audit_report,
        )
        reused_result = existing_result.model_copy(
            update={
                "reused_from_session": True,
                "warnings": [*existing_result.warnings, EDITORIAL_PLAN_SESSION_REUSE_MESSAGE],
                "audit_passed": audit.passed,
            }
        )
        return EditorialPlanGenerationRun(result=reused_result, fingerprint=fingerprint, audit=audit, reused=True)

    service = EditorialPlanService(openai_service)
    result = service.generate_editorial_plan(
        candidate_profile,
        market_analysis,
        compatibility_report,
        audit_report,
        output_language,
        status_callback=status_callback,
    )
    audit = None
    if result.success and result.professional_brand_plan is not None:
        audit = audit_editorial_plan(
            result.professional_brand_plan,
            candidate_profile,
            market_analysis,
            compatibility_report,
            audit_report,
        )
    return EditorialPlanGenerationRun(result=result, fingerprint=fingerprint if result.success else None, audit=audit, reused=False)
