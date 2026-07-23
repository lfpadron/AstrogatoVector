"""Programmatic LinkedIn banner rendering with Pillow."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from pydantic import ValidationError

from schemas.banner_models import (
    ALLOWED_BANNER_TEMPLATE_IDS,
    BANNER_MARGIN_BOTTOM,
    BANNER_MARGIN_RIGHT,
    BANNER_MARGIN_TOP,
    BANNER_RENDERER_VERSION,
    BANNER_TEXT_START_X,
    DEFAULT_BANNER_FILENAME,
    LINKEDIN_BANNER_FORMAT,
    LINKEDIN_BANNER_HEIGHT,
    LINKEDIN_BANNER_WIDTH,
    MAX_PRIMARY_LINES,
    MAX_SPECIALTY_LINES,
    MAX_SUPPORTING_LINES,
    MAX_TOTAL_BANNER_LINES,
    MIN_LARGE_TEXT_CONTRAST_RATIO,
    MIN_PRIMARY_FONT_SIZE,
    MIN_SPECIALTY_FONT_SIZE,
    MIN_SUPPORTING_FONT_SIZE,
    MIN_TEXT_CONTRAST_RATIO,
    PRIMARY_TO_SPECIALTY_GAP,
    PROFILE_PHOTO_SAFE_ZONE,
    RECOMMENDED_PRIMARY_CHARS,
    RECOMMENDED_SPECIALTY_CHARS,
    RECOMMENDED_SUPPORTING_CHARS,
    SPECIALTY_TO_SUPPORTING_GAP,
    BannerRenderInput,
    BannerRenderResult,
    BannerTemplate,
    BannerTextBox,
)
from services.font_service import DEFAULT_FONT_NAMES, FONT_FALLBACK_WARNING, find_font_path, font_supports_text

BANNER_STYLE_OPTIONS = {
    "Profesional claro": "professional_light",
    "Profesional oscuro": "professional_dark",
    "Ejecutivo azul": "executive_blue",
    "Tecnología limpia": "technology_clean",
}
BANNER_TEMPLATE_LABELS = {template_id: label for label, template_id in BANNER_STYLE_OPTIONS.items()}

TEXT_TOO_LONG_MESSAGE = (
    "El contenido del banner es demasiado extenso para mantener una lectura clara. "
    "Reduce el texto e intenta nuevamente."
)
INVALID_TEMPLATE_MESSAGE = "La plantilla seleccionada no es válida."
PILLOW_ERROR_MESSAGE = "No fue posible generar la imagen del banner."
CONTRAST_ERROR_MESSAGE = "La combinación visual no alcanzó un contraste suficiente."

_MEASURE_IMAGE = Image.new("RGB", (1, 1))
_MEASURE_DRAW = ImageDraw.Draw(_MEASURE_IMAGE)
_SEPARATOR_TOKENS = {"|", "·", "•", "-", ","}
_URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\s().-]?){9,}\d(?!\w)")
_RFC_PATTERN = re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)
_CURP_PATTERN = re.compile(r"\b[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE)


BANNER_TEMPLATES: dict[str, BannerTemplate] = {
    "professional_light": BannerTemplate(
        template_id="professional_light",
        display_name="Profesional claro",
        background_start="#F8FAFC",
        background_end="#DDE7F1",
        primary_text="#0B1F3A",
        secondary_text="#334155",
        accent="#9A3412",
        decorative_style="geometric_lines",
    ),
    "professional_dark": BannerTemplate(
        template_id="professional_dark",
        display_name="Profesional oscuro",
        background_start="#0B1220",
        background_end="#172A46",
        primary_text="#FFFFFF",
        secondary_text="#D6DEE9",
        accent="#FDBA74",
        decorative_style="abstract_shapes",
    ),
    "executive_blue": BannerTemplate(
        template_id="executive_blue",
        display_name="Ejecutivo azul",
        background_start="#071A33",
        background_end="#104E8B",
        primary_text="#FFFFFF",
        secondary_text="#D7E7F7",
        accent="#FDBA74",
        decorative_style="executive_lines",
    ),
    "technology_clean": BannerTemplate(
        template_id="technology_clean",
        display_name="Tecnología limpia",
        background_start="#263746",
        background_end="#42586B",
        primary_text="#F8FAFC",
        secondary_text="#D8E2EA",
        accent="#FDBA74",
        decorative_style="network_nodes",
    ),
}


@dataclass(frozen=True)
class _TextBlock:
    label: str
    lines: list[str]
    font: Any
    font_size: int
    line_height: int
    width: int
    height: int
    color: str


@dataclass(frozen=True)
class _TextLayout:
    primary: _TextBlock
    specialty: _TextBlock
    supporting: _TextBlock | None
    boxes: list[BannerTextBox]
    positions: dict[str, int]
    accent_color: str


class BannerService:
    """Render a LinkedIn banner PNG from already validated editable text."""

    def render_banner(self, render_input: BannerRenderInput | dict[str, Any]) -> BannerRenderResult:
        """Validate and render a banner entirely in memory."""
        try:
            normalized_input = BannerRenderInput.model_validate(render_input)
        except ValidationError as exc:
            return _failure_result(errors=_validation_error_messages(exc))

        fingerprint = build_banner_render_fingerprint(normalized_input)
        template = get_banner_template(normalized_input.template_id)
        if template is None:
            return _failure_result(
                errors=[INVALID_TEMPLATE_MESSAGE],
                template_id=normalized_input.template_id,
                fingerprint=fingerprint,
            )

        errors, warnings = validate_banner_content(normalized_input)
        if errors:
            return _failure_result(errors=errors, warnings=warnings, template_id=template.template_id, fingerprint=fingerprint)

        contrast_passed = validate_contrast(template)
        if not contrast_passed:
            return _failure_result(
                errors=[CONTRAST_ERROR_MESSAGE],
                warnings=warnings,
                template_id=template.template_id,
                fingerprint=fingerprint,
            )

        try:
            image = create_gradient_background(
                LINKEDIN_BANNER_WIDTH,
                LINKEDIN_BANNER_HEIGHT,
                template.background_start,
                template.background_end,
            )
            image = draw_decorative_elements(image, template, normalized_input.visual_concept)
            layout = fit_text_block(normalized_input, template, warnings)
            if layout is None:
                return _failure_result(
                    errors=[TEXT_TOO_LONG_MESSAGE],
                    warnings=warnings,
                    template_id=template.template_id,
                    fingerprint=fingerprint,
                )

            safe_zone_passed = validate_safe_zone(layout.boxes)
            overflow_passed = validate_overflow(layout.boxes)
            if not safe_zone_passed or not overflow_passed:
                return _failure_result(
                    errors=[TEXT_TOO_LONG_MESSAGE],
                    warnings=warnings,
                    template_id=template.template_id,
                    fingerprint=fingerprint,
                    safe_zone_passed=safe_zone_passed,
                    overflow_passed=overflow_passed,
                )

            draw_text_layout(image, layout)
            image_bytes = save_image_to_bytes(image)
        except (OSError, ValueError, UnicodeError):
            return _failure_result(
                errors=[PILLOW_ERROR_MESSAGE],
                warnings=warnings,
                template_id=template.template_id,
                fingerprint=fingerprint,
            )

        return BannerRenderResult(
            success=True,
            image_bytes=image_bytes,
            template_id=template.template_id,
            filename=DEFAULT_BANNER_FILENAME,
            fingerprint=fingerprint,
            primary_font_size=layout.primary.font_size,
            specialty_font_size=layout.specialty.font_size,
            supporting_font_size=layout.supporting.font_size if layout.supporting else None,
            primary_line_count=len(layout.primary.lines),
            specialty_line_count=len(layout.specialty.lines),
            supporting_line_count=len(layout.supporting.lines) if layout.supporting else 0,
            contrast_passed=True,
            overflow_passed=True,
            safe_zone_passed=True,
            warnings=warnings,
            text_bounding_boxes=layout.boxes,
        )


def build_banner_render_input_from_edit_state(
    edit_state: dict[str, Any],
    output_language: str,
) -> BannerRenderInput:
    """Create render input from Streamlit's editable LinkedIn profile state."""
    banner = edit_state.get("banner", {}) if isinstance(edit_state, dict) else {}
    return BannerRenderInput(
        primary_line=banner.get("primary_line", ""),
        specialty_line=banner.get("specialty_line", ""),
        supporting_line=banner.get("supporting_line") or None,
        visual_concept=banner.get("visual_concept") or None,
        template_id=banner.get("recommended_template", ""),
        output_language=output_language,
    )


def build_banner_render_fingerprint(render_input: BannerRenderInput) -> str:
    """Return a deterministic fingerprint for reuse inside one Streamlit session."""
    payload = {
        "primary_line": render_input.primary_line,
        "specialty_line": render_input.specialty_line,
        "supporting_line": render_input.supporting_line or "",
        "visual_concept": render_input.visual_concept or "",
        "template_id": render_input.template_id,
        "width": LINKEDIN_BANNER_WIDTH,
        "height": LINKEDIN_BANNER_HEIGHT,
        "renderer_version": BANNER_RENDERER_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_banner_template(template_id: str) -> BannerTemplate | None:
    """Return a configured template by id."""
    return BANNER_TEMPLATES.get(template_id)


def validate_banner_content(render_input: BannerRenderInput) -> tuple[list[str], list[str]]:
    """Run deterministic, local content checks before rendering."""
    errors: list[str] = []
    warnings: list[str] = []
    text_parts = [
        render_input.primary_line,
        render_input.specialty_line,
        render_input.supporting_line or "",
        render_input.visual_concept or "",
    ]
    joined = "\n".join(text_parts)

    if render_input.template_id not in ALLOWED_BANNER_TEMPLATE_IDS:
        errors.append(INVALID_TEMPLATE_MESSAGE)
    if _EMAIL_PATTERN.search(joined):
        errors.append("El banner no debe incluir correo electrónico.")
    if _PHONE_PATTERN.search(joined):
        errors.append("El banner no debe incluir teléfono.")
    if _RFC_PATTERN.search(joined):
        errors.append("El banner no debe incluir RFC.")
    if _CURP_PATTERN.search(joined):
        errors.append("El banner no debe incluir CURP.")
    if _URL_PATTERN.search(joined):
        warnings.append("Evita incluir URLs en el banner; LinkedIn ya muestra enlaces en zonas propias del perfil.")

    if len(render_input.primary_line.replace("\n", " ")) > RECOMMENDED_PRIMARY_CHARS:
        warnings.append("La línea principal supera la longitud recomendada de 70 caracteres.")
    if len(render_input.specialty_line.replace("\n", " ")) > RECOMMENDED_SPECIALTY_CHARS:
        warnings.append("La línea de especialidades supera la longitud recomendada de 130 caracteres.")
    if render_input.supporting_line and len(render_input.supporting_line.replace("\n", " ")) > RECOMMENDED_SUPPORTING_CHARS:
        warnings.append("La línea de apoyo supera la longitud recomendada de 110 caracteres.")

    return _unique_preserving_order(errors), _unique_preserving_order(warnings)


def create_gradient_background(width: int, height: int, start_hex: str, end_hex: str) -> Image.Image:
    """Create a horizontal RGB gradient background."""
    start = _hex_to_rgb(start_hex)
    end = _hex_to_rgb(end_hex)
    image = Image.new("RGB", (width, height), start)
    draw = ImageDraw.Draw(image)
    denominator = max(width - 1, 1)
    for x in range(width):
        ratio = x / denominator
        color = _interpolate_color(start, end, ratio)
        draw.line([(x, 0), (x, height)], fill=color)
    return image


def draw_decorative_elements(
    image: Image.Image,
    template: BannerTemplate,
    visual_concept: str | None = None,
) -> Image.Image:
    """Draw low-opacity vector-style accents without relying on external assets."""
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    accent = _hex_to_rgb(template.accent)
    secondary = _hex_to_rgb(template.secondary_text)
    style = _decorative_style(template.decorative_style, visual_concept)

    if style == "network_nodes":
        _draw_network_nodes(draw, accent, secondary)
    elif style == "executive_lines":
        _draw_executive_lines(draw, accent, secondary)
    elif style == "abstract_shapes":
        _draw_abstract_shapes(draw, accent, secondary)
    else:
        _draw_geometric_lines(draw, accent, secondary)

    base.alpha_composite(overlay)
    return base.convert("RGB")


def fit_text_block(
    render_input: BannerRenderInput,
    template: BannerTemplate,
    warnings: list[str] | None = None,
) -> _TextLayout | None:
    """Find the largest readable text layout that fits the banner bounds."""
    warnings = warnings if warnings is not None else []
    max_width = LINKEDIN_BANNER_WIDTH - BANNER_TEXT_START_X - BANNER_MARGIN_RIGHT
    max_height = LINKEDIN_BANNER_HEIGHT - BANNER_MARGIN_TOP - BANNER_MARGIN_BOTTOM
    regular_path = find_font_path(DEFAULT_FONT_NAMES, bold=False)
    bold_path = find_font_path(DEFAULT_FONT_NAMES, bold=True) or regular_path
    if regular_path is None and bold_path is None and FONT_FALLBACK_WARNING not in warnings:
        warnings.append(FONT_FALLBACK_WARNING)

    supporting_sizes = (
        range(template.supporting_font_size, MIN_SUPPORTING_FONT_SIZE - 1, -1)
        if render_input.supporting_line
        else [template.supporting_font_size]
    )
    for primary_size in range(template.primary_font_size, MIN_PRIMARY_FONT_SIZE - 1, -1):
        primary = _fit_single_block(
            "primary",
            render_input.primary_line,
            bold_path,
            primary_size,
            max_width,
            MAX_PRIMARY_LINES,
            template.primary_text,
        )
        if primary is None:
            continue
        for specialty_size in range(template.specialty_font_size, MIN_SPECIALTY_FONT_SIZE - 1, -1):
            specialty = _fit_single_block(
                "specialty",
                render_input.specialty_line,
                regular_path,
                specialty_size,
                max_width,
                MAX_SPECIALTY_LINES,
                template.secondary_text,
            )
            if specialty is None:
                continue
            for supporting_size in supporting_sizes:
                supporting = None
                if render_input.supporting_line:
                    supporting = _fit_single_block(
                        "supporting",
                        render_input.supporting_line,
                        regular_path,
                        supporting_size,
                        max_width,
                        MAX_SUPPORTING_LINES,
                        template.secondary_text,
                    )
                    if supporting is None:
                        continue
                blocks = [primary, specialty, *([supporting] if supporting else [])]
                if sum(len(block.lines) for block in blocks) > MAX_TOTAL_BANNER_LINES:
                    continue
                total_height = _layout_height(primary, specialty, supporting)
                if total_height > max_height:
                    continue
                layout = _position_text_blocks(primary, specialty, supporting, total_height, template.accent)
                if layout and validate_safe_zone(layout.boxes) and validate_overflow(layout.boxes):
                    _warn_if_font_support_is_uncertain(blocks, render_input, warnings)
                    return layout
    return None


def wrap_text_to_width(text: str, font: Any, max_width: int, max_lines: int) -> list[str] | None:
    """Wrap text by words and manual line breaks without splitting words."""
    wrapped_lines: list[str] = []
    for segment in text.split("\n"):
        segment = segment.strip()
        if not segment:
            continue
        segment_lines = _wrap_segment(segment, font, max_width)
        if segment_lines is None:
            return None
        wrapped_lines.extend(segment_lines)
    if not wrapped_lines or len(wrapped_lines) > max_lines:
        return None
    return wrapped_lines


def find_best_font_size(
    text: str,
    max_width: int,
    max_lines: int,
    initial_size: int,
    minimum_size: int,
    *,
    bold: bool = False,
) -> tuple[int, list[str]] | None:
    """Return the largest font size and wrapped lines that fit the width."""
    path = find_font_path(DEFAULT_FONT_NAMES, bold=bold)
    for size in range(initial_size, minimum_size - 1, -1):
        font = _load_font(path, size)
        lines = wrap_text_to_width(text, font, max_width, max_lines)
        if lines is not None:
            return size, lines
    return None


def measure_multiline_text(lines: list[str], font: Any, line_height: int | None = None) -> tuple[int, int]:
    """Measure multiline text in pixels."""
    widths = [_measure_line(line, font)[0] for line in lines]
    if not lines:
        return 0, 0
    resolved_line_height = line_height or _line_height(font, 18)
    return max(widths), resolved_line_height * len(lines)


def validate_safe_zone(boxes: list[BannerTextBox]) -> bool:
    """Check that text boxes do not intersect LinkedIn's conservative profile-photo zone."""
    safe = (
        PROFILE_PHOTO_SAFE_ZONE["x"],
        PROFILE_PHOTO_SAFE_ZONE["y"],
        PROFILE_PHOTO_SAFE_ZONE["x"] + PROFILE_PHOTO_SAFE_ZONE["width"],
        PROFILE_PHOTO_SAFE_ZONE["y"] + PROFILE_PHOTO_SAFE_ZONE["height"],
    )
    return not any(_boxes_intersect(_box_tuple(box), safe) for box in boxes)


def validate_overflow(boxes: list[BannerTextBox]) -> bool:
    """Check canvas bounds and text block overlap."""
    for box in boxes:
        if box.x < 0 or box.y < 0:
            return False
        if box.x + box.width > LINKEDIN_BANNER_WIDTH or box.y + box.height > LINKEDIN_BANNER_HEIGHT:
            return False
    for index, box in enumerate(boxes):
        for other in boxes[index + 1 :]:
            if _boxes_intersect(_box_tuple(box), _box_tuple(other)):
                return False
    return True


def validate_contrast(template: BannerTemplate) -> bool:
    """Validate representative template contrast for text and accents."""
    background = _average_color(_hex_to_rgb(template.background_start), _hex_to_rgb(template.background_end))
    primary_ratio = contrast_ratio(_hex_to_rgb(template.primary_text), background)
    secondary_ratio = contrast_ratio(_hex_to_rgb(template.secondary_text), background)
    accent_ratio = contrast_ratio(_hex_to_rgb(template.accent), background)
    return (
        primary_ratio >= MIN_LARGE_TEXT_CONTRAST_RATIO
        and secondary_ratio >= MIN_TEXT_CONTRAST_RATIO
        and accent_ratio >= MIN_LARGE_TEXT_CONTRAST_RATIO
    )


def contrast_ratio(foreground: tuple[int, int, int], background: tuple[int, int, int]) -> float:
    """Calculate contrast ratio using relative luminance."""
    foreground_luminance = _relative_luminance(foreground)
    background_luminance = _relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def save_image_to_bytes(image: Image.Image) -> bytes:
    """Serialize a Pillow image as PNG bytes without writing to disk."""
    buffer = io.BytesIO()
    image.save(buffer, format=LINKEDIN_BANNER_FORMAT, optimize=True)
    return buffer.getvalue()


def draw_text_layout(image: Image.Image, layout: _TextLayout) -> None:
    """Draw text and a subtle accent bar on the banner image."""
    draw = ImageDraw.Draw(image)
    block_top = min(box.y for box in layout.boxes)
    block_bottom = max(box.y + box.height for box in layout.boxes)
    accent_x = BANNER_TEXT_START_X - 24
    draw.rounded_rectangle(
        [accent_x, block_top + 2, accent_x + 6, block_bottom - 2],
        radius=3,
        fill=layout.accent_color,
    )
    for block in (layout.primary, layout.specialty, layout.supporting):
        if block is None:
            continue
        y = layout.positions[block.label]
        for line in block.lines:
            draw.text((BANNER_TEXT_START_X, y), line, font=block.font, fill=block.color)
            y += block.line_height


def _fit_single_block(
    label: str,
    text: str,
    font_path: str | None,
    font_size: int,
    max_width: int,
    max_lines: int,
    color: str,
) -> _TextBlock | None:
    font = _load_font(font_path, font_size)
    lines = wrap_text_to_width(text, font, max_width, max_lines)
    if lines is None:
        return None
    line_height = _line_height(font, font_size)
    width, height = measure_multiline_text(lines, font, line_height)
    if width > max_width:
        return None
    return _TextBlock(label, lines, font, font_size, line_height, width, height, color)


def _position_text_blocks(
    primary: _TextBlock,
    specialty: _TextBlock,
    supporting: _TextBlock | None,
    total_height: int,
    accent_color: str,
) -> _TextLayout | None:
    start_y = max(BANNER_MARGIN_TOP, (LINKEDIN_BANNER_HEIGHT - total_height) // 2)
    if start_y + total_height > LINKEDIN_BANNER_HEIGHT - BANNER_MARGIN_BOTTOM:
        start_y = LINKEDIN_BANNER_HEIGHT - BANNER_MARGIN_BOTTOM - total_height
    if start_y < BANNER_MARGIN_TOP:
        return None

    positions = {"primary": start_y}
    specialty_y = start_y + primary.height + PRIMARY_TO_SPECIALTY_GAP
    positions["specialty"] = specialty_y
    if supporting:
        positions["supporting"] = specialty_y + specialty.height + SPECIALTY_TO_SUPPORTING_GAP

    boxes = [
        _block_bbox(primary, positions["primary"]),
        _block_bbox(specialty, positions["specialty"]),
    ]
    if supporting:
        boxes.append(_block_bbox(supporting, positions["supporting"]))
    return _TextLayout(
        primary=primary,
        specialty=specialty,
        supporting=supporting,
        boxes=boxes,
        positions=positions,
        accent_color=accent_color,
    )


def _block_bbox(block: _TextBlock, y: int) -> BannerTextBox:
    line_boxes = []
    current_y = y
    for line in block.lines:
        bbox = _MEASURE_DRAW.textbbox((BANNER_TEXT_START_X, current_y), line, font=block.font)
        line_boxes.append(bbox)
        current_y += block.line_height
    left = min(box[0] for box in line_boxes)
    top = min(box[1] for box in line_boxes)
    right = max(box[2] for box in line_boxes)
    bottom = max(box[3] for box in line_boxes)
    return BannerTextBox(label=block.label, x=left, y=top, width=right - left, height=bottom - top)


def _layout_height(primary: _TextBlock, specialty: _TextBlock, supporting: _TextBlock | None) -> int:
    height = primary.height + PRIMARY_TO_SPECIALTY_GAP + specialty.height
    if supporting:
        height += SPECIALTY_TO_SUPPORTING_GAP + supporting.height
    return height


def _wrap_segment(segment: str, font: Any, max_width: int) -> list[str] | None:
    units = _group_separator_units(segment)
    lines: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current} {unit}"
        if _measure_line(candidate, font)[0] <= max_width:
            current = candidate
            continue
        if not current or _measure_line(unit, font)[0] > max_width:
            return None
        lines.append(current)
        current = unit
    if current:
        lines.append(current)
    if any(_line_has_edge_separator(line) for line in lines):
        return None
    return lines


def _group_separator_units(segment: str) -> list[str]:
    tokens = segment.split()
    units: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _SEPARATOR_TOKENS and units and index + 1 < len(tokens):
            units[-1] = f"{units[-1]} {token} {tokens[index + 1]}"
            index += 2
            continue
        if token.endswith(",") and index + 1 < len(tokens):
            units.append(f"{token} {tokens[index + 1]}")
            index += 2
            continue
        units.append(token)
        index += 1
    return units


def _line_has_edge_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and (stripped[0] in _SEPARATOR_TOKENS or stripped[-1] in _SEPARATOR_TOKENS)


def _load_font(path: str | None, size: int) -> Any:
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _warn_if_font_support_is_uncertain(
    blocks: list[_TextBlock],
    render_input: BannerRenderInput,
    warnings: list[str],
) -> None:
    text = "\n".join(
        [
            render_input.primary_line,
            render_input.specialty_line,
            render_input.supporting_line or "",
        ]
    )
    for block in blocks:
        if not font_supports_text(block.font, text):
            message = "La fuente seleccionada podría no representar todos los caracteres del banner."
            if message not in warnings:
                warnings.append(message)
            return


def _decorative_style(default_style: str, visual_concept: str | None) -> str:
    normalized = (visual_concept or "").casefold()
    if any(term in normalized for term in ("network", "nodes", "data", "technology", "tecnologia", "datos")):
        return "network_nodes"
    if any(term in normalized for term in ("executive", "ejecutiv")):
        return "executive_lines"
    if any(term in normalized for term in ("orbit", "vector", "geometric", "geometr")):
        return "geometric_lines"
    return default_style


def _draw_geometric_lines(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    draw.arc([-150, 28, 390, 360], 315, 60, fill=(*accent, 70), width=3)
    draw.arc([-95, 75, 315, 330], 310, 70, fill=(*secondary, 40), width=2)
    for offset in (0, 44, 88):
        draw.line([(74 + offset, 60), (320 + offset, 266)], fill=(*secondary, 36), width=2)
    draw.line([(1320, 74), (1515, 42)], fill=(*accent, 42), width=3)


def _draw_abstract_shapes(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    draw.ellipse([-90, -60, 245, 270], outline=(*secondary, 42), width=3)
    draw.ellipse([104, 96, 235, 227], outline=(*accent, 70), width=4)
    draw.rounded_rectangle([1360, 54, 1610, 176], radius=24, outline=(*accent, 36), width=3)
    draw.line([(72, 318), (360, 232)], fill=(*secondary, 36), width=3)


def _draw_executive_lines(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    for x in (430, 452, 474):
        draw.line([(x, 0), (x - 92, 396)], fill=(*secondary, 28), width=2)
    draw.line([(472, 38), (472, 310)], fill=(*accent, 66), width=3)
    draw.line([(1375, 0), (1530, 396)], fill=(*secondary, 24), width=3)


def _draw_network_nodes(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    nodes = [(74, 64), (188, 112), (315, 78), (128, 248), (284, 286), (410, 226)]
    for start, end in zip(nodes, nodes[1:]):
        draw.line([start, end], fill=(*secondary, 45), width=2)
    for index, node in enumerate(nodes):
        radius = 6 if index % 2 else 8
        color = accent if index in {1, 4} else secondary
        draw.ellipse(
            [node[0] - radius, node[1] - radius, node[0] + radius, node[1] + radius],
            fill=(*color, 78),
        )
    for x in range(40, 430, 72):
        draw.line([(x, 18), (x, 350)], fill=(*secondary, 14), width=1)


def _measure_line(line: str, font: Any) -> tuple[int, int]:
    bbox = _MEASURE_DRAW.textbbox((0, 0), line, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _line_height(font: Any, size: int) -> int:
    measured_height = _measure_line("Ag", font)[1]
    return max(measured_height + 6, int(size * 1.18))


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(f"Invalid color: {value}")
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _interpolate_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    return tuple(round(start[index] + (end[index] - start[index]) * ratio) for index in range(3))


def _average_color(start: tuple[int, int, int], end: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(round((start[index] + end[index]) / 2) for index in range(3))


def _relative_luminance(color: tuple[int, int, int]) -> float:
    channels = []
    for value in color:
        normalized = value / 255
        channels.append(normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4)
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722


def _box_tuple(box: BannerTextBox) -> tuple[int, int, int, int]:
    return box.x, box.y, box.x + box.width, box.y + box.height


def _boxes_intersect(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> bool:
    return first[0] < second[2] and first[2] > second[0] and first[1] < second[3] and first[3] > second[1]


def _validation_error_messages(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        error_type = str(error.get("type", ""))
        message = str(error.get("msg", ""))
        if error_type == "string_too_long":
            messages.append(TEXT_TOO_LONG_MESSAGE)
        elif "saltos manuales" in message:
            messages.append("No uses más de dos saltos manuales por campo.")
        elif location == "primary_line":
            messages.append("La línea principal del banner es obligatoria.")
        elif location == "specialty_line":
            messages.append("La línea de especialidades del banner es obligatoria.")
        elif location == "template_id":
            messages.append(INVALID_TEMPLATE_MESSAGE)
        else:
            messages.append("El contenido del banner no es válido.")
    return _unique_preserving_order(messages)


def _failure_result(
    *,
    errors: list[str],
    warnings: list[str] | None = None,
    template_id: str | None = None,
    fingerprint: str | None = None,
    safe_zone_passed: bool = False,
    overflow_passed: bool = False,
) -> BannerRenderResult:
    return BannerRenderResult(
        success=False,
        template_id=template_id,
        fingerprint=fingerprint,
        warnings=warnings or [],
        errors=_unique_preserving_order(errors),
        safe_zone_passed=safe_zone_passed,
        overflow_passed=overflow_passed,
    )


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
