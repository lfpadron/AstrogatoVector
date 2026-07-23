"""Models for target job market analysis results and audits."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.market_models import TargetMarketAnalysis


class JobAnalysisAuditFinding(StrictBaseModel):
    """One deterministic audit finding for target market analysis."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1000)


class JobAnalysisAuditResult(StrictBaseModel):
    """Deterministic audit result for target market analysis."""

    passed: bool
    findings: list[JobAnalysisAuditFinding] = Field(default_factory=list)


class JobAnalysisResult(StrictBaseModel):
    """Safe result for the target jobs analysis stage."""

    success: bool
    market_analysis: TargetMarketAnalysis | None = None
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
    def validate_result_consistency(self) -> JobAnalysisResult:
        if self.success and self.market_analysis is None:
            raise ValueError("successful job analysis must include market_analysis")
        if not self.success and self.market_analysis is not None:
            raise ValueError("failed job analysis cannot include market_analysis")
        if self.success and not self.audit_passed:
            raise ValueError("successful job analysis must pass audit")
        return self
