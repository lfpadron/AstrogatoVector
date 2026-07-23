"""Models for candidate extraction, privacy filtering and evidence audits."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.evidence_models import CandidateProfessionalProfile


class PrivacyFilterResult(StrictBaseModel):
    """Result of a limited preventive redaction pass."""

    filtered_text: str
    redaction_count: int = Field(ge=0)
    detected_categories: list[str] = Field(default_factory=list)


class EvidenceAuditFinding(StrictBaseModel):
    """One deterministic evidence audit finding."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1000)


class EvidenceAuditResult(StrictBaseModel):
    """Deterministic audit result for an extracted candidate profile."""

    passed: bool
    findings: list[EvidenceAuditFinding] = Field(default_factory=list)


class CandidateExtractionResult(StrictBaseModel):
    """Safe result for the candidate extraction stage."""

    success: bool
    profile: CandidateProfessionalProfile | None = None
    model_used: str | None = None
    request_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    evidence_audit_passed: bool = False
    evidence_audit_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None
    user_message: str | None = None
    retryable: bool = False
    reused_from_session: bool = False

    @model_validator(mode="after")
    def validate_result_consistency(self) -> CandidateExtractionResult:
        if self.success and self.profile is None:
            raise ValueError("successful candidate extraction must include a profile")
        if not self.success and self.profile is not None:
            raise ValueError("failed candidate extraction cannot include a profile")
        if self.success and not self.evidence_audit_passed:
            raise ValueError("successful candidate extraction must pass evidence audit")
        return self
