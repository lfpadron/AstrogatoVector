"""Models for targeted CV generation, audits and exports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import EvidenceStatus, OutputLanguage, SkillCategory
from schemas.evidence_models import EvidenceItem

TARGETED_CV_VERSION = "1.0"
TARGETED_CV_PROMPT_VERSION = "1.0"
TARGETED_CV_EXPORT_VERSION = "1.0"
TARGETED_CV_ATS_METHODOLOGY_VERSION = "1.0"

TARGETED_CV_ATS_WEIGHTS = {
    "keyword_coverage": 0.30,
    "requirement_coverage": 0.25,
    "skills_coverage": 0.15,
    "title_alignment": 0.10,
    "readability": 0.10,
    "consistency": 0.10,
}

TargetedCVContentSource = Literal["generated-and-audited", "user-edited"]


class TargetedCVHeader(StrictBaseModel):
    """Public header content for one targeted CV."""

    candidate_name: str | None = Field(default=None, max_length=160)
    professional_title: str = Field(min_length=1, max_length=200)
    target_role_title: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=80)
    linkedin_url: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=180)


class TargetedCVSummary(StrictBaseModel):
    """Profile summary written for a specific target job."""

    text: str = Field(min_length=1, max_length=1200)
    included_keywords: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)


class TargetedCVSkill(StrictBaseModel):
    """One CV skill selected from supported professional evidence."""

    name: str = Field(min_length=1, max_length=120)
    category: SkillCategory
    priority: int = Field(ge=1, le=50)
    evidence_status: EvidenceStatus
    source_evidence: list[EvidenceItem] = Field(default_factory=list)
    used_in_sections: list[str] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)


class TargetedCVBullet(StrictBaseModel):
    """One evidence-backed bullet for a targeted CV experience entry."""

    text: str = Field(min_length=1, max_length=700)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    included_keywords: list[str] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)


class TargetedCVExperienceEntry(StrictBaseModel):
    """One source employment entry adapted for a target job."""

    source_role_title: str = Field(min_length=1, max_length=200)
    display_role_title: str = Field(min_length=1, max_length=200)
    employer: str = Field(min_length=1, max_length=200)
    start_date: str | None = Field(default=None, max_length=80)
    end_date: str | None = Field(default=None, max_length=80)
    is_current: bool = False
    location: str | None = Field(default=None, max_length=200)
    included: bool = True
    exclusion_reason: str | None = Field(default=None, max_length=500)
    bullets: list[TargetedCVBullet] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_exclusion_reason(self) -> TargetedCVExperienceEntry:
        if not self.included and not self.exclusion_reason:
            raise ValueError("excluded experience entries require exclusion_reason")
        return self


class EducationEntry(StrictBaseModel):
    """Education item displayed in a targeted CV when supported."""

    text: str = Field(min_length=1, max_length=500)
    visible: bool = True
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)


class CertificationEntry(StrictBaseModel):
    """Certification item displayed in a targeted CV when supported."""

    text: str = Field(min_length=1, max_length=500)
    visible: bool = True
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)


class LanguageEntry(StrictBaseModel):
    """Language item displayed in a targeted CV when supported."""

    text: str = Field(min_length=1, max_length=500)
    visible: bool = True
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)


class TargetedCV(StrictBaseModel):
    """Export-ready CV for one analyzed target vacancy."""

    cv_version: str = TARGETED_CV_VERSION
    prompt_version: str = TARGETED_CV_PROMPT_VERSION
    export_version: str = TARGETED_CV_EXPORT_VERSION
    output_language: OutputLanguage
    generated_at: datetime
    content_source: TargetedCVContentSource = "generated-and-audited"
    target_job_index: int = Field(ge=1, le=6)
    target_job_title: str = Field(min_length=1, max_length=200)
    target_company: str | None = Field(default=None, max_length=200)
    header: TargetedCVHeader
    summary: TargetedCVSummary
    skills: list[TargetedCVSkill] = Field(default_factory=list)
    experience: list[TargetedCVExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    ats_keywords_used: list[str] = Field(default_factory=list)
    ats_keywords_missing: list[str] = Field(default_factory=list)
    ats_keywords_omitted: list[str] = Field(default_factory=list)
    overall_review_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target_consistency(self) -> TargetedCV:
        if self.header.target_role_title.casefold() != self.target_job_title.casefold():
            raise ValueError("header target_role_title must match target_job_title")
        return self


class TargetedCVAuditFinding(StrictBaseModel):
    """One deterministic audit finding for a targeted CV."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1000)


class TargetedCVAuditResult(StrictBaseModel):
    """Deterministic audit result for one targeted CV."""

    passed: bool
    findings: list[TargetedCVAuditFinding] = Field(default_factory=list)


class TargetedCVATSAudit(StrictBaseModel):
    """Local ATS-oriented audit for one targeted CV."""

    job_index: int = Field(ge=1, le=6)
    overall_score: float = Field(ge=0.0, le=100.0)
    component_scores: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=lambda: dict(TARGETED_CV_ATS_WEIGHTS))
    supported_keywords: list[str] = Field(default_factory=list)
    keywords_used: list[str] = Field(default_factory=list)
    missing_supported_keywords: list[str] = Field(default_factory=list)
    unsupported_keywords_removed: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    methodology_version: str = TARGETED_CV_ATS_METHODOLOGY_VERSION

    @model_validator(mode="after")
    def validate_score_components(self) -> TargetedCVATSAudit:
        expected = set(TARGETED_CV_ATS_WEIGHTS)
        if set(self.weights) != expected:
            raise ValueError("ATS weights must include all targeted CV components")
        if set(self.component_scores) != expected:
            raise ValueError("ATS component_scores must include all targeted CV components")
        if abs(sum(self.weights.values()) - 1.0) > 0.000001:
            raise ValueError("ATS weights must sum to 1.0")
        for component, score in self.component_scores.items():
            if score < 0 or score > 100:
                raise ValueError(f"{component} score must be between 0 and 100")
        return self


class TargetedCVEditableValidationResult(StrictBaseModel):
    """Result of validating user edits before export."""

    passed: bool
    findings: list[TargetedCVAuditFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TargetedCVGenerationResult(StrictBaseModel):
    """Safe result for one targeted CV generation call."""

    success: bool
    targeted_cv: TargetedCV | None = None
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
    prompt_version: str | None = TARGETED_CV_PROMPT_VERSION

    @model_validator(mode="after")
    def validate_result_consistency(self) -> TargetedCVGenerationResult:
        if self.success and self.targeted_cv is None:
            raise ValueError("successful targeted CV generation must include targeted_cv")
        if not self.success and self.targeted_cv is not None:
            raise ValueError("failed targeted CV generation cannot include targeted_cv")
        if self.success and not self.audit_passed:
            raise ValueError("successful targeted CV generation must pass audit")
        return self
