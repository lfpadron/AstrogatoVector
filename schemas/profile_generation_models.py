"""Models for LinkedIn profile generation results and local audits."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.profile_models import LinkedInProfileOutput


class LinkedInProfileAuditFinding(StrictBaseModel):
    """One deterministic finding for generated LinkedIn profile output."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1000)


class LinkedInProfileAuditResult(StrictBaseModel):
    """Deterministic audit result for LinkedIn profile generation."""

    passed: bool
    findings: list[LinkedInProfileAuditFinding] = Field(default_factory=list)


class LinkedInProfileGenerationResult(StrictBaseModel):
    """Safe result for the LinkedIn profile generation stage."""

    success: bool
    profile_output: LinkedInProfileOutput | None = None
    model_used: str | None = None
    request_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    audit_passed: bool = False
    audit_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None
    user_message: str | None = None
    retryable: bool = False
    reused_from_session: bool = False
    prompt_version: str | None = None

    @model_validator(mode="after")
    def validate_result_consistency(self) -> LinkedInProfileGenerationResult:
        if self.success and self.profile_output is None:
            raise ValueError("successful LinkedIn profile generation must include profile_output")
        if not self.success and self.profile_output is not None:
            raise ValueError("failed LinkedIn profile generation cannot include profile_output")
        if self.success and not self.audit_passed:
            raise ValueError("successful LinkedIn profile generation must pass audit")
        return self
