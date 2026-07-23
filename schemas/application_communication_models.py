"""Models for per-vacancy application communications."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import EvidenceStatus, OutputLanguage

APPLICATION_COMMUNICATION_VERSION = "1.0"
APPLICATION_COMMUNICATION_PROMPT_VERSION = "1.0"
APPLICATION_COMMUNICATION_EXPORT_VERSION = "1.0"


class GreetingStrategy(str, Enum):
    """Supported greeting strategies for outbound application materials."""

    NAMED_PERSON = "named_person"
    HIRING_TEAM = "hiring_team"
    RECRUITING_TEAM = "recruiting_team"
    COMPANY_TEAM = "company_team"
    GENERAL = "general"


class CommunicationClaim(StrictBaseModel):
    """One claim used in application copy and its evidence handling."""

    text: str = Field(min_length=1, max_length=600)
    evidence_status: EvidenceStatus
    evidence_sources: list[str] = Field(default_factory=list)
    needs_review: bool = False
    usage_context: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_claim_evidence(self) -> CommunicationClaim:
        if self.evidence_status == EvidenceStatus.SUPPORTED.value and not self.evidence_sources:
            raise ValueError("SUPPORTED communication claims require evidence_sources")
        if self.evidence_status in {EvidenceStatus.MISSING.value, EvidenceStatus.CONFLICT.value} and not self.needs_review:
            raise ValueError("MISSING or CONFLICT communication claims must be marked for review")
        return self


class CoverLetterOutput(StrictBaseModel):
    """Cover letter generated for one vacancy."""

    greeting_strategy: GreetingStrategy
    greeting: str = Field(min_length=1, max_length=200)
    full_text: str = Field(min_length=1, max_length=6000)
    sign_off: str = Field(min_length=1, max_length=220)
    word_count: int = Field(ge=1, le=900)
    keywords_used: list[str] = Field(default_factory=list)
    strengths_used: list[str] = Field(default_factory=list)
    claims: list[CommunicationClaim] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)


class RecruiterMessageOutput(StrictBaseModel):
    """Short recruiter message generated for one vacancy."""

    message: str = Field(min_length=1, max_length=1200)
    character_count: int = Field(ge=1, le=1200)
    call_to_action: str = Field(min_length=1, max_length=260)
    keywords_used: list[str] = Field(default_factory=list)
    strengths_used: list[str] = Field(default_factory=list)
    claims: list[CommunicationClaim] = Field(default_factory=list)
    personalization_notes: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)


class ApplicationEmailOutput(StrictBaseModel):
    """Application email generated for one vacancy."""

    subject_options: list[str] = Field(min_length=1, max_length=3)
    greeting_strategy: GreetingStrategy
    greeting: str = Field(min_length=1, max_length=200)
    full_text: str = Field(min_length=1, max_length=4500)
    sign_off: str = Field(min_length=1, max_length=220)
    attachments_mentioned: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=1, le=700)
    call_to_action: str = Field(min_length=1, max_length=260)
    keywords_used: list[str] = Field(default_factory=list)
    strengths_used: list[str] = Field(default_factory=list)
    claims: list[CommunicationClaim] = Field(default_factory=list)
    personalization_notes: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)


class ApplicationCommunicationKit(StrictBaseModel):
    """Complete communication kit for one target vacancy."""

    communication_version: str = APPLICATION_COMMUNICATION_VERSION
    prompt_version: str = APPLICATION_COMMUNICATION_PROMPT_VERSION
    export_version: str = APPLICATION_COMMUNICATION_EXPORT_VERSION
    output_language: OutputLanguage
    generated_at: datetime
    target_job_index: int = Field(ge=1, le=6)
    target_job_title: str = Field(min_length=1, max_length=200)
    target_company: str | None = Field(default=None, max_length=200)
    compatibility_score: float | None = Field(default=None, ge=0.0, le=100.0)
    compatibility_band: str | None = Field(default=None, max_length=80)
    targeted_cv_version: str | None = Field(default=None, max_length=40)
    cover_letter: CoverLetterOutput
    recruiter_message: RecruiterMessageOutput
    application_email: ApplicationEmailOutput
    subject_options: list[str] = Field(default_factory=list)
    calls_to_action: list[str] = Field(default_factory=list)
    personalization_notes: list[str] = Field(default_factory=list)
    risks_or_claims_requiring_review: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_subjects_consistency(self) -> ApplicationCommunicationKit:
        if self.subject_options and self.subject_options != self.application_email.subject_options:
            raise ValueError("subject_options must match application_email.subject_options when provided")
        if not self.subject_options:
            self.subject_options = list(self.application_email.subject_options)
        return self


class ApplicationCommunicationAuditFinding(StrictBaseModel):
    """One local audit finding for an application communication kit."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1200)


class ApplicationCommunicationAuditResult(StrictBaseModel):
    """Deterministic audit result for one application communication kit."""

    passed: bool
    findings: list[ApplicationCommunicationAuditFinding] = Field(default_factory=list)
    word_counts: dict[str, int] = Field(default_factory=dict)
    character_counts: dict[str, int] = Field(default_factory=dict)
    audited_at: datetime = Field(default_factory=datetime.now)


class CommunicationRedundancyAuditResult(StrictBaseModel):
    """Local heuristic redundancy audit across communication pieces and CV."""

    passed: bool
    findings: list[ApplicationCommunicationAuditFinding] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    audited_at: datetime = Field(default_factory=datetime.now)


class ApplicationCommunicationEditValidationResult(StrictBaseModel):
    """Result of validating user edits without calling external services."""

    passed: bool
    findings: list[ApplicationCommunicationAuditFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.now)


class ApplicationCommunicationGenerationResult(StrictBaseModel):
    """Safe generation result for one per-vacancy communication kit."""

    success: bool
    communication_kit: ApplicationCommunicationKit | None = None
    model_used: str | None = None
    request_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    audit_passed: bool = False
    redundancy_audit_passed: bool = False
    audit_findings: list[str] = Field(default_factory=list)
    redundancy_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None
    user_message: str | None = None
    retryable: bool = False
    reused_from_session: bool = False
    prompt_version: str | None = APPLICATION_COMMUNICATION_PROMPT_VERSION

    @model_validator(mode="after")
    def validate_result_consistency(self) -> ApplicationCommunicationGenerationResult:
        if self.success and self.communication_kit is None:
            raise ValueError("successful communication generation must include communication_kit")
        if not self.success and self.communication_kit is not None:
            raise ValueError("failed communication generation cannot include communication_kit")
        if self.success and (not self.audit_passed or not self.redundancy_audit_passed):
            raise ValueError("successful communication generation must pass all local audits")
        return self
