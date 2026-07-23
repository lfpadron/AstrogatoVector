"""Input and local extraction models for Astrogato Vector."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import ContentSource, OutputLanguage

CV_SOURCES = {ContentSource.TEXT, ContentSource.DOCX, ContentSource.PDF, "text", "docx", "pdf"}
DOCUMENT_FILE_SOURCES = {ContentSource.DOCX, ContentSource.PDF, "docx", "pdf"}
LINKEDIN_SOURCES = {ContentSource.TEXT, ContentSource.URL, ContentSource.GENERATED, "text", "url", "generated"}
JOB_SOURCES = {ContentSource.TEXT, ContentSource.URL, "text", "url"}


class DocumentParseResult(StrictBaseModel):
    """Detailed result from local document parsing."""

    success: bool = Field(description="Whether local text extraction succeeded.")
    filename: str = Field(min_length=1, description="Original uploaded filename.")
    file_type: Literal["docx", "pdf", "unknown"] = Field(description="Detected file type.")
    extracted_text: str = Field(default="", description="Raw extracted text kept only in memory.")
    normalized_text: str = Field(default="", description="Normalized extracted text kept only in memory.")
    character_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    page_count: int | None = Field(default=None, ge=0)
    paragraph_count: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    likely_scanned: bool = False


class DocumentParseSummary(StrictBaseModel):
    """Safe document parsing summary stored with the validated input."""

    source: ContentSource = Field(description="Effective CV source used by the app.")
    filename: str | None = Field(default=None, description="Uploaded filename when a document was used.")
    file_type: ContentSource | None = Field(default=None, description="Document file type when applicable.")
    character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=0)
    paragraph_count: int | None = Field(default=None, ge=0)
    likely_scanned: bool = False
    warnings: list[str] = Field(default_factory=list)

    @field_validator("source")
    @classmethod
    def source_must_be_cv_source(cls, value: ContentSource) -> ContentSource:
        if value not in CV_SOURCES:
            raise ValueError("source must be text, docx or pdf")
        return value

    @field_validator("file_type")
    @classmethod
    def file_type_must_be_document_source(cls, value: ContentSource | None) -> ContentSource | None:
        if value is not None and value not in DOCUMENT_FILE_SOURCES:
            raise ValueError("file_type must be docx or pdf")
        return value


class LinkReadSummary(StrictBaseModel):
    """Safe link reading summary stored without HTML or raw response bytes."""

    requested_url: str = Field(min_length=1)
    final_url: str | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    page_title: str | None = None
    character_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    likely_login_page: bool = False
    likely_dynamic_page: bool = False
    access_restricted: bool = False


class LinkReadResult(StrictBaseModel):
    """Detailed result from a controlled public text page fetch."""

    success: bool
    requested_url: str = Field(min_length=1)
    final_url: str | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    page_title: str | None = None
    extracted_text: str = ""
    normalized_text: str = ""
    character_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    likely_login_page: bool = False
    likely_dynamic_page: bool = False
    access_restricted: bool = False

    def to_summary(self) -> LinkReadSummary:
        """Return a text-free summary that can be stored in validated input."""
        return LinkReadSummary(
            requested_url=self.requested_url,
            final_url=self.final_url,
            status_code=self.status_code,
            content_type=self.content_type,
            page_title=self.page_title,
            character_count=self.character_count,
            word_count=self.word_count,
            warnings=self.warnings,
            likely_login_page=self.likely_login_page,
            likely_dynamic_page=self.likely_dynamic_page,
            access_restricted=self.access_restricted,
        )


class JobInput(StrictBaseModel):
    """Validated target job input prepared for future processing."""

    index: int = Field(ge=1, le=6, description="Visible order of the job in the form.")
    title: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    description: str = Field(min_length=100, description="Effective job text from pasted text or URL.")
    source: ContentSource = Field(description="Effective source: text or url.")
    url: str | None = None
    link_summary: LinkReadSummary | None = None

    @field_validator("source")
    @classmethod
    def source_must_be_text_or_url(cls, value: ContentSource) -> ContentSource:
        if value not in JOB_SOURCES:
            raise ValueError("job source must be text or url")
        return value

    @model_validator(mode="after")
    def validate_source_details(self) -> JobInput:
        if self.source == ContentSource.URL and not self.url:
            raise ValueError("url is required when job source is url")
        return self


class CandidateInput(StrictBaseModel):
    """Normalized candidate input consumed by future AI stages."""

    cv_text: str = Field(min_length=200, description="Effective CV text kept in session only.")
    cv_source: ContentSource = Field(description="Effective CV source: text, docx or pdf.")
    cv_filename: str | None = None
    cv_file_size: int | None = Field(default=None, ge=0)
    cv_parse_summary: DocumentParseSummary | None = None
    linkedin_text: str | None = None
    linkedin_source: ContentSource = Field(description="Effective LinkedIn source.")
    linkedin_url: str | None = None
    linkedin_link_summary: LinkReadSummary | None = None
    output_language: OutputLanguage
    jobs: list[JobInput] = Field(min_length=2, max_length=6)

    @field_validator("cv_source")
    @classmethod
    def cv_source_must_be_valid(cls, value: ContentSource) -> ContentSource:
        if value not in CV_SOURCES:
            raise ValueError("cv_source must be text, docx or pdf")
        return value

    @field_validator("linkedin_source")
    @classmethod
    def linkedin_source_must_be_valid(cls, value: ContentSource) -> ContentSource:
        if value not in LINKEDIN_SOURCES:
            raise ValueError("linkedin_source must be text, url or generated")
        return value

    @model_validator(mode="after")
    def validate_candidate_input(self) -> CandidateInput:
        if self.cv_source in DOCUMENT_FILE_SOURCES and self.cv_parse_summary is None:
            raise ValueError("cv_parse_summary is required when CV comes from a document")

        if self.linkedin_source == ContentSource.TEXT and not self.linkedin_text:
            raise ValueError("linkedin_text is required when linkedin_source is text")

        if self.linkedin_source == ContentSource.URL:
            if not self.linkedin_url:
                raise ValueError("linkedin_url is required when linkedin_source is url")
            if not self.linkedin_text:
                raise ValueError("linkedin_text is required when linkedin_source is url")

        indices = [job.index for job in self.jobs]
        if len(indices) != len(set(indices)):
            raise ValueError("job indices must be unique")

        expected_indices = list(range(1, len(indices) + 1))
        if sorted(indices) != expected_indices:
            raise ValueError("job indices must be consecutive starting at 1")

        return self
