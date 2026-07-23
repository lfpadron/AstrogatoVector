"""Final audit orchestration without Streamlit dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_models import LinkedInProfileOutput
from services.final_audit_service import (
    FINAL_AUDIT_MISSING_STAGES_MESSAGE,
    build_final_audit_fingerprint,
    FinalAuditService,
)

SESSION_REUSE_MESSAGE = (
    "Se reutilizó la auditoría integral porque el perfil, el mercado, LinkedIn y la compatibilidad no cambiaron."
)


@dataclass(frozen=True)
class FinalAuditRun:
    """Result of one final audit orchestration attempt."""

    result: AuditReport
    fingerprint: str | None = None
    reused: bool = False


def run_final_audit_pipeline(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    compatibility_report: CompatibilityReport,
    *,
    existing_result: AuditReport | None = None,
    existing_fingerprint: str | None = None,
    force: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> FinalAuditRun:
    """Run or reuse the local final audit for current structured outputs."""
    fingerprint = build_final_audit_fingerprint(
        candidate_profile,
        market_analysis,
        linkedin_profile,
        compatibility_report,
    )
    if (
        not force
        and existing_fingerprint == fingerprint
        and existing_result is not None
        and existing_result.success
        and existing_result.linkedin_positioning is not None
        and existing_result.ats_estimation is not None
    ):
        return FinalAuditRun(
            result=existing_result.model_copy(
                update={
                    "reused_from_session": True,
                    "warnings": [*existing_result.warnings, SESSION_REUSE_MESSAGE],
                }
            ),
            fingerprint=fingerprint,
            reused=True,
        )

    result = FinalAuditService().generate_report(
        candidate_profile,
        market_analysis,
        linkedin_profile,
        compatibility_report,
        status_callback=status_callback,
    )
    return FinalAuditRun(result=result, fingerprint=fingerprint if result.success else None, reused=False)


def missing_final_audit_result() -> AuditReport:
    """Return a safe missing-prerequisites final audit result."""
    return AuditReport(
        success=False,
        audit_passed=False,
        error_category="missing_previous_stages",
        user_message=FINAL_AUDIT_MISSING_STAGES_MESSAGE,
        retryable=False,
    )
