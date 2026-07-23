"""PDF exporter for targeted CVs."""

from __future__ import annotations

import html
from io import BytesIO
from typing import Any

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from schemas.targeted_cv_models import TargetedCV


class TargetedCVPDFExporter:
    """Export one targeted CV to selectable PDF bytes."""

    def export(self, targeted_cv: TargetedCV) -> bytes:
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=LETTER,
            leftMargin=0.7 * inch,
            rightMargin=0.7 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            title=targeted_cv.header.professional_title,
        )
        styles = _styles()
        story: list[Any] = []
        _append_header(story, targeted_cv, styles)
        _append_heading(story, "Perfil profesional", styles)
        story.append(Paragraph(_escape(targeted_cv.summary.text), styles["Body"]))
        _append_heading(story, "Competencias clave", styles)
        _append_bullets(story, [skill.name for skill in sorted(targeted_cv.skills, key=lambda item: item.priority)], styles)
        _append_heading(story, "Experiencia profesional", styles)
        for entry in targeted_cv.experience:
            if not entry.included:
                continue
            story.append(Paragraph(_escape(f"{entry.display_role_title} | {entry.employer}"), styles["Subheading"]))
            details = " | ".join(value for value in [_date_line(entry.start_date, entry.end_date), entry.location] if value)
            if details:
                story.append(Paragraph(_escape(details), styles["Small"]))
            _append_bullets(story, [bullet.text for bullet in entry.bullets], styles)
        _append_optional_section(story, "Educación", [entry.text for entry in targeted_cv.education if entry.visible], styles)
        _append_optional_section(
            story,
            "Certificaciones",
            [entry.text for entry in targeted_cv.certifications if entry.visible],
            styles,
        )
        _append_optional_section(story, "Idiomas", [entry.text for entry in targeted_cv.languages if entry.visible], styles)
        doc.build(story)
        return output.getvalue()


def _append_header(story: list[Any], targeted_cv: TargetedCV, styles: dict[str, ParagraphStyle]) -> None:
    header = targeted_cv.header
    story.append(Paragraph(_escape(header.candidate_name or header.professional_title), styles["Title"]))
    story.append(Paragraph(_escape(header.professional_title), styles["Subtitle"]))
    contact = " | ".join(value for value in [header.location, header.email, header.phone, header.linkedin_url] if value)
    if contact:
        story.append(Paragraph(_escape(contact), styles["Contact"]))
    story.append(Spacer(1, 0.12 * inch))


def _append_heading(story: list[Any], title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(_escape(title.upper()), styles["Heading"]))


def _append_optional_section(story: list[Any], title: str, values: list[str], styles: dict[str, ParagraphStyle]) -> None:
    if not values:
        return
    _append_heading(story, title, styles)
    _append_bullets(story, values, styles)


def _append_bullets(story: list[Any], values: list[str], styles: dict[str, ParagraphStyle]) -> None:
    for value in values:
        if value.strip():
            story.append(Paragraph(f"- {_escape(value)}", styles["Bullet"]))


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "TargetedCVTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            textColor="#000000",
            spaceAfter=4,
        ),
        "Subtitle": ParagraphStyle(
            "TargetedCVSubtitle",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "Contact": ParagraphStyle(
            "TargetedCVContact",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "Heading": ParagraphStyle(
            "TargetedCVHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
            textColor="#000000",
            spaceBefore=4,
            spaceAfter=3,
        ),
        "Subheading": ParagraphStyle(
            "TargetedCVSubheading",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=3,
            spaceAfter=1,
        ),
        "Body": ParagraphStyle(
            "TargetedCVBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=4,
        ),
        "Small": ParagraphStyle(
            "TargetedCVSmall",
            parent=sample["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            spaceAfter=2,
        ),
        "Bullet": ParagraphStyle(
            "TargetedCVBullet",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            leftIndent=10,
            firstLineIndent=-7,
            spaceAfter=1,
        ),
    }


def _date_line(start_date: str | None, end_date: str | None) -> str:
    if start_date and end_date:
        return f"{start_date} - {end_date}"
    if start_date:
        return f"{start_date} - Actual"
    return end_date or ""


def _escape(value: str) -> str:
    return html.escape(value or "")
