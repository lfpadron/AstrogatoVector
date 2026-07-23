"""Models for semantic compatibility analysis and execution metadata."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.compatibility_models import CompatibilityReport
from schemas.enums import EvidenceStatus, PriorityLevel, RequirementCoverage, SkillCategory
from schemas.evidence_models import EvidenceItem


class SemanticRequirementMatch(StrictBaseModel):
    """Semantic coverage assigned before deterministic scoring."""

    job_index: int = Field(ge=1, le=6)
    requirement_name: str = Field(min_length=1, max_length=300)
    normalized_requirement: str = Field(min_length=1, max_length=300)
    category: SkillCategory
    required: bool
    priority: PriorityLevel
    coverage: RequirementCoverage
    candidate_evidence_status: EvidenceStatus
    candidate_evidence: list[EvidenceItem] = Field(default_factory=list)
    matched_candidate_items: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1, max_length=1200)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_semantic_match(self) -> SemanticRequirementMatch:
        if self.coverage == RequirementCoverage.FULL.value and self.candidate_evidence_status != EvidenceStatus.SUPPORTED.value:
            raise ValueError("full coverage requires SUPPORTED candidate_evidence_status")
        if self.coverage == RequirementCoverage.MISSING.value and self.candidate_evidence:
            raise ValueError("missing coverage cannot include candidate_evidence")
        if self.coverage == RequirementCoverage.CONFLICT.value and not self.explanation:
            raise ValueError("conflict coverage requires explanation")
        return self


class JobCompatibilitySemanticEvaluation(StrictBaseModel):
    """Semantic evaluation for one target job."""

    job_index: int = Field(ge=1, le=6)
    job_title: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    requirement_matches: list[SemanticRequirementMatch] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    development_opportunities: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=1600)


class CompatibilitySemanticEvaluation(StrictBaseModel):
    """OpenAI semantic output for all target jobs."""

    job_evaluations: list[JobCompatibilitySemanticEvaluation] = Field(min_length=2, max_length=6)
    global_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_job_indices(self) -> CompatibilitySemanticEvaluation:
        indices = [evaluation.job_index for evaluation in self.job_evaluations]
        if len(indices) != len(set(indices)):
            raise ValueError("job_evaluations must have unique job_index values")
        return self


class CompatibilityAuditFinding(StrictBaseModel):
    """One deterministic compatibility audit finding."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1000)


class CompatibilityAuditResult(StrictBaseModel):
    """Deterministic audit result for semantic and mathematical compatibility."""

    passed: bool
    findings: list[CompatibilityAuditFinding] = Field(default_factory=list)


class CompatibilityAnalysisResult(StrictBaseModel):
    """Safe result for the compatibility analysis stage."""

    success: bool
    semantic_evaluation: CompatibilitySemanticEvaluation | None = None
    compatibility_report: CompatibilityReport | None = None
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
    methodology_version: str | None = None

    @model_validator(mode="after")
    def validate_result_consistency(self) -> CompatibilityAnalysisResult:
        if self.success and self.semantic_evaluation is None:
            raise ValueError("successful compatibility analysis must include semantic_evaluation")
        if self.success and self.compatibility_report is None:
            raise ValueError("successful compatibility analysis must include compatibility_report")
        if self.success and not self.audit_passed:
            raise ValueError("successful compatibility analysis must pass audit")
        if not self.success and self.semantic_evaluation is not None:
            raise ValueError("failed compatibility analysis cannot expose semantic_evaluation")
        if not self.success and self.compatibility_report is not None:
            raise ValueError("failed compatibility analysis cannot expose compatibility_report")
        return self
