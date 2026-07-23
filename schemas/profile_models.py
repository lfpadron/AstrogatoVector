"""LinkedIn profile output models for future generation stages."""

from __future__ import annotations

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import EvidenceStatus, PriorityLevel, SkillCategory


class BannerContent(StrictBaseModel):
    """Textual banner concept; no image generation in this contract."""

    primary_line: str = Field(min_length=3, max_length=90)
    specialty_line: str = Field(min_length=3, max_length=140)
    supporting_line: str | None = Field(default=None, max_length=140)
    visual_concept: str = Field(min_length=1, max_length=300)
    recommended_template: str = Field(
        min_length=1,
        max_length=120,
        description="Identificador de plantilla, por ejemplo professional_light.",
    )


class HeadlineOutput(StrictBaseModel):
    """LinkedIn headline with exact character count."""

    text: str = Field(min_length=20, max_length=220)
    character_count: int | None = None
    included_keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_character_count(self) -> HeadlineOutput:
        object.__setattr__(self, "character_count", len(self.text))
        return self


class AboutOutput(StrictBaseModel):
    """LinkedIn About section."""

    text: str = Field(min_length=200, max_length=3000)
    character_count: int | None = None
    included_keywords: list[str] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_character_count(self) -> AboutOutput:
        object.__setattr__(self, "character_count", len(self.text))
        return self


class RewrittenExperienceEntry(StrictBaseModel):
    """Suggested rewrite for one profile experience entry."""

    source_role_title: str = Field(min_length=1, max_length=200)
    suggested_role_title: str = Field(min_length=1, max_length=200)
    employer: str = Field(min_length=1, max_length=200)
    rewritten_text: str = Field(min_length=50, max_length=3000)
    included_keywords: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class PrioritizedSkill(StrictBaseModel):
    """Skill recommended for prominent placement in LinkedIn."""

    name: str = Field(min_length=1, max_length=120)
    category: SkillCategory
    priority_rank: int = Field(ge=1, le=50)
    evidence_status: EvidenceStatus
    rationale: str = Field(min_length=1, max_length=1000)
    recommended_placement: list[str] = Field(default_factory=list)


class ATSKeyword(StrictBaseModel):
    """Keyword recommended for ATS-oriented wording."""

    keyword: str = Field(min_length=1, max_length=120)
    normalized_keyword: str = Field(min_length=1, max_length=120)
    priority: PriorityLevel
    frequency_in_jobs: int = Field(ge=1, le=6)
    supported_by_candidate: bool
    evidence_status: EvidenceStatus
    recommended_sections: list[str] = Field(default_factory=list)


class LinkedInProfileOutput(StrictBaseModel):
    """Complete LinkedIn profile output contract."""

    banner: BannerContent
    headline: HeadlineOutput
    about: AboutOutput
    experience: list[RewrittenExperienceEntry] = Field(default_factory=list)
    prioritized_skills: list[PrioritizedSkill] = Field(default_factory=list)
    ats_keywords: list[ATSKeyword] = Field(default_factory=list)
    global_review_notes: list[str] = Field(default_factory=list)
