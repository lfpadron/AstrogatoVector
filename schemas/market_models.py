"""Target market and job analysis models."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import PriorityLevel, SeniorityLevel, SkillCategory


class JobRequirement(StrictBaseModel):
    """A requirement extracted from one or more job postings."""

    name: str = Field(min_length=1, max_length=200)
    normalized_name: str = Field(min_length=1, max_length=200)
    category: SkillCategory
    description: str = Field(min_length=1, max_length=800)
    required: bool
    importance: PriorityLevel
    exact_keywords: list[str] = Field(default_factory=list)


class JobAnalysis(StrictBaseModel):
    """Structured analysis of one target job posting."""

    job_index: int = Field(ge=1, le=6)
    title: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    inferred_seniority: SeniorityLevel
    role_summary: str = Field(min_length=20, max_length=2000)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[JobRequirement] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    leadership_skills: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    language_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    exact_keywords: list[str] = Field(default_factory=list)


class MarketKeyword(StrictBaseModel):
    """Keyword consolidated across the target job set."""

    keyword: str = Field(min_length=1, max_length=120)
    normalized_keyword: str = Field(min_length=1, max_length=120)
    frequency: int = Field(ge=1, le=6)
    job_indices: list[int] = Field(default_factory=list)
    category: SkillCategory
    priority: PriorityLevel

    @field_validator("job_indices")
    @classmethod
    def validate_job_indices(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("job_indices must not contain duplicates")
        if any(index < 1 or index > 6 for index in values):
            raise ValueError("job_indices must be between 1 and 6")
        return values

    @model_validator(mode="after")
    def validate_frequency(self) -> MarketKeyword:
        if self.job_indices and self.frequency != len(set(self.job_indices)):
            raise ValueError("frequency must match the number of unique job indices")
        return self


class TargetMarketAnalysis(StrictBaseModel):
    """Consolidated analysis of the target job market."""

    target_role_family: str = Field(min_length=2, max_length=200)
    suggested_target_titles: list[str] = Field(default_factory=list)
    dominant_seniority: SeniorityLevel
    market_summary: str = Field(min_length=20, max_length=3000)
    common_responsibilities: list[str] = Field(default_factory=list)
    common_requirements: list[JobRequirement] = Field(default_factory=list)
    keywords: list[MarketKeyword] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    leadership_skills: list[str] = Field(default_factory=list)
    business_skills: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    job_analyses: list[JobAnalysis] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_job_analysis_indices(self) -> TargetMarketAnalysis:
        indices = [analysis.job_index for analysis in self.job_analyses]
        if len(indices) != len(set(indices)):
            raise ValueError("job_analyses must have unique job_index values")
        return self
