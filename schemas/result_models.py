"""Top-level application result model."""

from __future__ import annotations

from pydantic import Field

from schemas.audit_models import AuditReport
from schemas.base import StrictBaseModel
from schemas.communication_models import CommunicationOutput
from schemas.compatibility_models import CompatibilityReport
from schemas.content_models import FourWeekContentPlan
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_models import LinkedInProfileOutput


class ApplicationResult(StrictBaseModel):
    """Complete structured output for Astrogato Vector."""

    schema_version: str = Field(default="1.0", description="Astrogato Vector schema version.")
    output_language: OutputLanguage
    candidate_profile: CandidateProfessionalProfile
    target_market: TargetMarketAnalysis
    linkedin_profile: LinkedInProfileOutput
    compatibility: CompatibilityReport
    audits: AuditReport
    communication: CommunicationOutput
    content_plan: FourWeekContentPlan
    global_warnings: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    generated_with_ai: bool = True
    disclaimer: str = Field(min_length=20, max_length=1500)
