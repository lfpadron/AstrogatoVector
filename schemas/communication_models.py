"""Professional communication output models."""

from __future__ import annotations

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import ProfessionalMessageType


class ProfessionalMessage(StrictBaseModel):
    """Short professional outreach message."""

    message_type: ProfessionalMessageType
    purpose: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=20, max_length=3000)
    target_role: str | None = Field(default=None, max_length=200)
    target_company: str | None = Field(default=None, max_length=200)
    personalization_required: list[str] = Field(default_factory=list)


class CoverLetter(StrictBaseModel):
    """Cover letter tailored to one target job."""

    job_index: int = Field(ge=1, le=6)
    job_title: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=200, max_length=5000)
    evidence_used: list[str] = Field(default_factory=list)
    gaps_not_claimed: list[str] = Field(default_factory=list)
    personalization_required: list[str] = Field(default_factory=list)


class CommunicationOutput(StrictBaseModel):
    """Headhunter messages and one cover letter per target job."""

    headhunter_messages: list[ProfessionalMessage] = Field(default_factory=list)
    cover_letters: list[CoverLetter] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_unique_letters(self) -> CommunicationOutput:
        indices = [letter.job_index for letter in self.cover_letters]
        if len(indices) != len(set(indices)):
            raise ValueError("cover letters must have unique job_index values")
        return self

    def validate_for_job_indices(self, expected_job_indices: list[int]) -> None:
        """Validate that this output contains exactly one cover letter per expected job."""
        actual = sorted(letter.job_index for letter in self.cover_letters)
        expected = sorted(expected_job_indices)
        if actual != expected:
            raise ValueError("cover letters must match the expected job indices")
