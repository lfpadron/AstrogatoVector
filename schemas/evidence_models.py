"""Professional evidence models for future AI extraction."""

from __future__ import annotations

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import EvidenceStatus, SeniorityLevel, SkillCategory

SUPPORTED_VALUES = {EvidenceStatus.SUPPORTED, EvidenceStatus.SUPPORTED.value}
CONFLICT_VALUES = {EvidenceStatus.CONFLICT, EvidenceStatus.CONFLICT.value}


class EvidenceReference(StrictBaseModel):
    """Short reference to the source text that supports a claim."""

    source_section: str = Field(
        min_length=1,
        max_length=120,
        description="Sección del CV o perfil donde se encontró la evidencia.",
    )
    source_excerpt: str = Field(
        min_length=1,
        max_length=500,
        description="Fragmento breve que respalda la afirmación.",
    )


class EvidenceItem(StrictBaseModel):
    """One professional claim with evidence status and confidence."""

    statement: str = Field(min_length=1, max_length=800)
    status: EvidenceStatus
    category: SkillCategory | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    references: list[EvidenceReference] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_evidence_state(self) -> EvidenceItem:
        if self.status in SUPPORTED_VALUES and not self.references:
            raise ValueError("SUPPORTED evidence must include at least one reference")
        if self.status in CONFLICT_VALUES and not self.notes:
            raise ValueError("CONFLICT evidence must include notes")
        return self


class Achievement(StrictBaseModel):
    """Professional achievement without invented metrics."""

    description: str = Field(min_length=1, max_length=1000)
    measurable_result: str | None = Field(default=None, max_length=500)
    evidence_status: EvidenceStatus
    references: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_supported_achievement(self) -> Achievement:
        if self.evidence_status in SUPPORTED_VALUES and not self.references:
            raise ValueError("SUPPORTED achievements must include at least one reference")
        return self


class CandidateSkill(StrictBaseModel):
    """Skill extracted from the candidate material."""

    name: str = Field(min_length=1, max_length=120)
    normalized_name: str = Field(min_length=1, max_length=120)
    category: SkillCategory
    evidence_status: EvidenceStatus
    confidence: float = Field(ge=0.0, le=1.0)
    years_experience: float | None = Field(default=None, ge=0)
    references: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_supported_skill(self) -> CandidateSkill:
        if self.evidence_status in SUPPORTED_VALUES and not self.references:
            raise ValueError("SUPPORTED skills must include at least one reference")
        return self


class EmploymentEntry(StrictBaseModel):
    """One employment entry from the candidate profile."""

    employer: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)
    start_date: str | None = Field(default=None, max_length=80)
    end_date: str | None = Field(default=None, max_length=80)
    is_current: bool = False
    location: str | None = Field(default=None, max_length=200)
    responsibilities: list[EvidenceItem] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    technologies: list[CandidateSkill] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)


class CandidateProfessionalProfile(StrictBaseModel):
    """Structured professional profile extracted from the normalized input."""

    professional_identity: str = Field(min_length=1, max_length=300)
    targetable_roles: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=20, max_length=3000)
    total_years_experience: float | None = Field(default=None, ge=0)
    seniority: SeniorityLevel
    industries: list[str] = Field(default_factory=list)
    employment_history: list[EmploymentEntry] = Field(default_factory=list)
    skills: list[CandidateSkill] = Field(default_factory=list)
    leadership_capabilities: list[EvidenceItem] = Field(default_factory=list)
    education: list[EvidenceItem] = Field(default_factory=list)
    certifications: list[EvidenceItem] = Field(default_factory=list)
    languages: list[EvidenceItem] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
