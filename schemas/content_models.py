"""LinkedIn content planning models."""

from __future__ import annotations

from collections import Counter

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel


class LinkedInPostSuggestion(StrictBaseModel):
    """One LinkedIn post suggestion in a four-week plan."""

    week: int = Field(ge=1, le=4)
    publication_number: int = Field(ge=1, le=2)
    theme: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    draft_text: str = Field(min_length=100, max_length=4000)
    call_to_action: str | None = Field(default=None, max_length=500)
    evidence_basis: list[str] = Field(default_factory=list)
    placeholders_to_complete: list[str] = Field(default_factory=list)
    suggested_hashtags: list[str] = Field(default_factory=list)


class FourWeekContentPlan(StrictBaseModel):
    """Exactly eight posts: two suggestions for each of four weeks."""

    posts: list[LinkedInPostSuggestion] = Field(min_length=8, max_length=8)
    editorial_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_calendar_structure(self) -> FourWeekContentPlan:
        week_counts = Counter(post.week for post in self.posts)
        if set(week_counts) != {1, 2, 3, 4}:
            raise ValueError("weeks 1 to 4 must be present")
        if any(count != 2 for count in week_counts.values()):
            raise ValueError("each week must have exactly two posts")

        combinations = [(post.week, post.publication_number) for post in self.posts]
        if len(combinations) != len(set(combinations)):
            raise ValueError("week/publication_number combinations must be unique")

        return self
