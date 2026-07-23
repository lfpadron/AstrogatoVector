"""OpenAI diagnostic schemas."""

from __future__ import annotations

from pydantic import Field

from schemas.base import StrictBaseModel
from schemas.enums import OutputLanguage


class DiagnosticCapability(StrictBaseModel):
    """One general future capability confirmed by the diagnostic call."""

    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=300)


class OpenAIDiagnosticResponse(StrictBaseModel):
    """Small structured response returned by the OpenAI diagnostic call."""

    operational: bool
    detected_language: OutputLanguage
    confirmation_message: str = Field(min_length=10, max_length=300)
    capabilities: list[DiagnosticCapability] = Field(min_length=3, max_length=3)
    human_review_warning: str = Field(min_length=20, max_length=500)


class OpenAIDiagnosticResult(StrictBaseModel):
    """Safe diagnostic result stored in Streamlit session state."""

    success: bool
    response: OpenAIDiagnosticResponse | None = None
    model_used: str | None = None
    request_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    error_category: str | None = None
    user_message: str | None = None
    retryable: bool = False
