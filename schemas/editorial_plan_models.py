"""Models for the four-week LinkedIn professional brand editorial plan."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import OutputLanguage

EDITORIAL_PLAN_VERSION = "1.0"
EDITORIAL_PLAN_PROMPT_VERSION = "1.0"
EDITORIAL_PLAN_EXPORT_VERSION = "1.0"


class EditorialObjective(str, Enum):
    """Allowed editorial objectives for each LinkedIn post."""

    AUTHORITY = "authority"
    EXPERIENCE = "experience"
    LEADERSHIP = "leadership"
    LEARNING = "learning"
    METHODOLOGY = "methodology"
    INNOVATION = "innovation"
    REFLECTION = "reflection"
    NETWORKING = "networking"


class LinkedInPostType(str, Enum):
    """Allowed professional post types."""

    PROFESSIONAL_STORY = "professional_story"
    LESSON_LEARNED = "lesson_learned"
    ERROR_TO_LEARNING = "error_to_learning"
    SUCCESS_CASE = "success_case"
    METHODOLOGY = "methodology"
    TECHNICAL_EXPLANATION = "technical_explanation"
    MARKET_TREND = "market_trend"
    PROFESSIONAL_OPINION = "professional_opinion"
    MINI_TUTORIAL = "mini_tutorial"
    REFLECTION = "reflection"


class EditorialDay(str, Enum):
    """Calendar day slots without absolute dates."""

    MONDAY = "monday"
    WEDNESDAY = "wednesday"
    FRIDAY = "friday"


class LinkedInPostFormat(str, Enum):
    """Length-oriented publication formats."""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class LinkedInPostPlan(StrictBaseModel):
    """One LinkedIn publication in the four-week plan."""

    week: int = Field(ge=1, le=4)
    day: EditorialDay
    title: str = Field(min_length=1, max_length=160)
    objective: EditorialObjective
    theme: str = Field(min_length=1, max_length=180)
    audience: str = Field(min_length=1, max_length=200)
    format: LinkedInPostFormat
    post_type: LinkedInPostType
    hook: str = Field(min_length=12, max_length=260)
    body: str = Field(min_length=300, max_length=2200)
    cta: str = Field(min_length=8, max_length=220)
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    keywords_used: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    claims_requiring_review: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    character_count: int = Field(ge=300, le=2200)

    @model_validator(mode="after")
    def validate_character_count(self) -> LinkedInPostPlan:
        if self.character_count != len(self.body.strip()):
            raise ValueError("character_count must match body length")
        return self


class EditorialCalendarWeek(StrictBaseModel):
    """One week with exactly three LinkedIn posts."""

    week: int = Field(ge=1, le=4)
    posts: list[LinkedInPostPlan] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_week_posts(self) -> EditorialCalendarWeek:
        if any(post.week != self.week for post in self.posts):
            raise ValueError("all posts must match the parent week")
        days = [post.day for post in self.posts]
        if set(days) != {EditorialDay.MONDAY.value, EditorialDay.WEDNESDAY.value, EditorialDay.FRIDAY.value}:
            raise ValueError("each week must include monday, wednesday and friday")
        if len(days) != len(set(days)):
            raise ValueError("post days must be unique within a week")
        return self


class EditorialCalendar(StrictBaseModel):
    """Exactly four weeks and twelve posts."""

    weeks: list[EditorialCalendarWeek] = Field(min_length=4, max_length=4)

    @property
    def posts(self) -> list[LinkedInPostPlan]:
        """Flatten posts in calendar order."""
        return [post for week in sorted(self.weeks, key=lambda item: item.week) for post in week.posts]

    @model_validator(mode="after")
    def validate_calendar(self) -> EditorialCalendar:
        week_numbers = [week.week for week in self.weeks]
        if set(week_numbers) != {1, 2, 3, 4}:
            raise ValueError("calendar must contain weeks 1 to 4")
        if len(week_numbers) != len(set(week_numbers)):
            raise ValueError("calendar weeks must be unique")
        posts = self.posts
        if len(posts) != 12:
            raise ValueError("editorial calendar must contain exactly 12 posts")
        slots = [(post.week, post.day) for post in posts]
        if len(slots) != len(set(slots)):
            raise ValueError("calendar slots must be unique")
        for previous, current in zip(posts, posts[1:]):
            if previous.theme.casefold().strip() == current.theme.casefold().strip():
                raise ValueError("two consecutive posts cannot use the same theme")
        formats = Counter(post.format for post in posts)
        if len(formats) < 2:
            raise ValueError("editorial plan must mix post formats")
        return self


class ProfessionalBrandPlan(StrictBaseModel):
    """Complete four-week LinkedIn professional brand editorial plan."""

    plan_version: str = EDITORIAL_PLAN_VERSION
    prompt_version: str = EDITORIAL_PLAN_PROMPT_VERSION
    export_version: str = EDITORIAL_PLAN_EXPORT_VERSION
    output_language: OutputLanguage
    generated_at: datetime
    summary: str = Field(min_length=1, max_length=2400)
    objectives: list[EditorialObjective] = Field(default_factory=list)
    calendar: EditorialCalendar
    strengths_exploited: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_plan_scope(self) -> ProfessionalBrandPlan:
        if len(self.calendar.posts) != 12:
            raise ValueError("professional brand plan must include exactly 12 posts")
        return self


class EditorialPlanAuditFinding(StrictBaseModel):
    """One deterministic finding for the editorial plan audit."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1200)


class EditorialPlanAuditResult(StrictBaseModel):
    """Local audit result for a professional brand plan."""

    passed: bool
    findings: list[EditorialPlanAuditFinding] = Field(default_factory=list)
    character_counts: dict[str, int] = Field(default_factory=dict)
    audited_at: datetime = Field(default_factory=datetime.now)


class EditorialPlanEditValidationResult(StrictBaseModel):
    """Result of validating editorial plan edits without external calls."""

    passed: bool
    findings: list[EditorialPlanAuditFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.now)


class EditorialPlanGenerationResult(StrictBaseModel):
    """Safe generation result for the four-week editorial plan."""

    success: bool
    professional_brand_plan: ProfessionalBrandPlan | None = None
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
    prompt_version: str | None = EDITORIAL_PLAN_PROMPT_VERSION

    @model_validator(mode="after")
    def validate_result_consistency(self) -> EditorialPlanGenerationResult:
        if self.success and self.professional_brand_plan is None:
            raise ValueError("successful editorial plan generation must include professional_brand_plan")
        if not self.success and self.professional_brand_plan is not None:
            raise ValueError("failed editorial plan generation cannot include professional_brand_plan")
        if self.success and not self.audit_passed:
            raise ValueError("successful editorial plan generation must pass local audit")
        return self
