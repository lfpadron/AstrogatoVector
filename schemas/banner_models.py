"""Local contracts for programmatic LinkedIn banner rendering."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator

from schemas.base import StrictBaseModel
from schemas.enums import OutputLanguage

LINKEDIN_BANNER_WIDTH = 1584
LINKEDIN_BANNER_HEIGHT = 396
LINKEDIN_BANNER_FORMAT = "PNG"
DEFAULT_BANNER_FILENAME = "astrogato-vector-linkedin-banner.png"
BANNER_RENDERER_VERSION = "1.0"

PROFILE_PHOTO_SAFE_ZONE = {
    "x": 0,
    "y": 150,
    "width": 420,
    "height": 246,
}
BANNER_MARGIN_TOP = 45
BANNER_MARGIN_RIGHT = 70
BANNER_MARGIN_BOTTOM = 45
BANNER_TEXT_START_X = 500

PRIMARY_FONT_SIZE = 48
SPECIALTY_FONT_SIZE = 28
SUPPORTING_FONT_SIZE = 22
MIN_PRIMARY_FONT_SIZE = 30
MIN_SPECIALTY_FONT_SIZE = 19
MIN_SUPPORTING_FONT_SIZE = 16
MAX_PRIMARY_LINES = 2
MAX_SPECIALTY_LINES = 2
MAX_SUPPORTING_LINES = 2
MAX_TOTAL_BANNER_LINES = 6
PRIMARY_TO_SPECIALTY_GAP = 18
SPECIALTY_TO_SUPPORTING_GAP = 12

MAX_BANNER_PRIMARY_CHARS = 120
MAX_BANNER_SPECIALTY_CHARS = 200
MAX_BANNER_SUPPORTING_CHARS = 200
RECOMMENDED_PRIMARY_CHARS = 70
RECOMMENDED_SPECIALTY_CHARS = 130
RECOMMENDED_SUPPORTING_CHARS = 110

MIN_TEXT_CONTRAST_RATIO = 4.5
MIN_LARGE_TEXT_CONTRAST_RATIO = 3.0

ALLOWED_BANNER_TEMPLATE_IDS = (
    "professional_light",
    "professional_dark",
    "executive_blue",
    "technology_clean",
)

_COLLAPSIBLE_SPACE_RE = re.compile(r"[ \t\f\v]+")


class BannerTemplate(StrictBaseModel):
    """Visual settings for a deterministic banner template."""

    template_id: str
    display_name: str
    background_start: str
    background_end: str
    primary_text: str
    secondary_text: str
    accent: str
    decorative_style: str
    alignment: Literal["left"] = "left"
    primary_font_size: int = Field(default=PRIMARY_FONT_SIZE, ge=MIN_PRIMARY_FONT_SIZE)
    specialty_font_size: int = Field(default=SPECIALTY_FONT_SIZE, ge=MIN_SPECIALTY_FONT_SIZE)
    supporting_font_size: int = Field(default=SUPPORTING_FONT_SIZE, ge=MIN_SUPPORTING_FONT_SIZE)


class BannerRenderInput(StrictBaseModel):
    """Editable banner content selected by the user for PNG rendering."""

    primary_line: str = Field(min_length=1, max_length=MAX_BANNER_PRIMARY_CHARS)
    specialty_line: str = Field(min_length=1, max_length=MAX_BANNER_SPECIALTY_CHARS)
    supporting_line: str | None = Field(default=None, max_length=MAX_BANNER_SUPPORTING_CHARS)
    template_id: str = Field(min_length=1, max_length=120)
    output_language: OutputLanguage
    visual_concept: str | None = Field(default=None, max_length=300)

    @field_validator("primary_line", "specialty_line", "supporting_line", "visual_concept", mode="before")
    @classmethod
    def normalize_text_field(cls, value: object, info: ValidationInfo) -> object:
        """Trim, collapse repeated spaces and preserve up to two manual line breaks."""
        if value is None:
            return None
        text = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
        if text.count("\n") > 2:
            raise ValueError("No uses mas de dos saltos manuales por campo.")
        lines = [_COLLAPSIBLE_SPACE_RE.sub(" ", line.strip()) for line in text.split("\n")]
        normalized = "\n".join(line for line in lines if line)
        if not normalized and info.field_name in {"supporting_line", "visual_concept"}:
            return None
        return normalized

    @field_validator("template_id", mode="before")
    @classmethod
    def normalize_template_id(cls, value: object) -> str:
        return str(value).strip()


class BannerTextBox(StrictBaseModel):
    """Internal text bounding box used by layout validation."""

    label: Literal["primary", "specialty", "supporting"]
    x: int
    y: int
    width: int
    height: int


class BannerRenderResult(StrictBaseModel):
    """Result summary for an in-memory rendered LinkedIn banner."""

    success: bool
    image_bytes: bytes | None = Field(default=None, exclude=True)
    width: int = LINKEDIN_BANNER_WIDTH
    height: int = LINKEDIN_BANNER_HEIGHT
    format: str = LINKEDIN_BANNER_FORMAT
    template_id: str | None = None
    filename: str | None = None
    fingerprint: str | None = None
    renderer_version: str = BANNER_RENDERER_VERSION
    primary_font_size: int | None = None
    specialty_font_size: int | None = None
    supporting_font_size: int | None = None
    primary_line_count: int = 0
    specialty_line_count: int = 0
    supporting_line_count: int = 0
    contrast_passed: bool = False
    overflow_passed: bool = False
    safe_zone_passed: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    text_bounding_boxes: list[BannerTextBox] = Field(default_factory=list, exclude=True)


class BannerAuditResult(StrictBaseModel):
    """Deterministic audit for a rendered banner PNG."""

    passed: bool
    dimensions_valid: bool
    contrast_valid: bool
    safe_zone_valid: bool
    overflow_valid: bool
    file_signature_valid: bool
    findings: list[str] = Field(default_factory=list)
