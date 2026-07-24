"""PDF exporter for LinkedIn professional editorial plans."""

from __future__ import annotations

import html
from io import BytesIO
from typing import Any

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from schemas.editorial_plan_models import LinkedInPostPlan, ProfessionalBrandPlan
from utils.filename_utils import safe_download_filename

EDITORIAL_PLAN_PDF_FILENAME = safe_download_filename("linkedin-editorial-plan", "pdf")


class EditorialPlanPDFExporter:
    """Export one professional brand plan to selectable PDF bytes."""

    def export(self, plan: ProfessionalBrandPlan) -> bytes:
        """Return PDF bytes."""
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=LETTER,
            leftMargin=0.72 * inch,
            rightMargin=0.72 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            title="Plan editorial profesional de LinkedIn",
        )
        styles = _styles()
        story: list[Any] = [
            Paragraph("Plan editorial profesional de LinkedIn", styles["Title"]),
            Paragraph("Borrador profesional para revisión humana y publicación manual.", styles["Small"]),
            Spacer(1, 0.08 * inch),
        ]
        _append_heading(story, "Resumen", styles, level=1)
        _append_paragraphs(story, plan.summary, styles)
        _append_list_section(story, "Objetivos", [str(item) for item in plan.objectives], styles)
        _append_list_section(story, "Fortalezas explotadas", plan.strengths_exploited, styles)
        _append_list_section(story, "Temas", plan.themes, styles)
        _append_list_section(story, "Riesgos", plan.risks, styles)
        _append_list_section(story, "Recomendaciones", plan.recommendations, styles)
        _append_heading(story, "Calendario editorial", styles, level=1)
        for week in sorted(plan.calendar.weeks, key=lambda item: item.week):
            _append_heading(story, f"Semana {week.week}", styles, level=2)
            for post in sorted(week.posts, key=_day_order):
                _append_post(story, post, styles)
        _append_heading(story, "Nota de uso", styles, level=1)
        _append_paragraphs(story, "Estos textos son orientativos. Revisa evidencia, tono y confidencialidad antes de publicarlos.", styles)
        doc.build(story)
        return output.getvalue()


def _append_post(story: list[Any], post: LinkedInPostPlan, styles: dict[str, ParagraphStyle]) -> None:
    _append_heading(story, f"{_day_label(post.day)} - {post.title}", styles, level=2)
    _append_paragraphs(
        story,
        (
            f"Semana {post.week} | Objetivo: {post.objective} | Tipo: {post.post_type} | "
            f"Formato: {post.format} | Caracteres: {post.character_count}"
        ),
        styles,
    )
    _append_paragraphs(story, f"Tema: {post.theme}", styles)
    _append_paragraphs(story, f"Audiencia: {post.audience}", styles)
    _append_label(story, "Hook", styles)
    _append_paragraphs(story, post.hook, styles)
    _append_label(story, "Texto", styles)
    _append_paragraphs(story, post.body, styles)
    _append_label(story, "CTA", styles)
    _append_paragraphs(story, post.cta, styles)
    _append_label(story, "Hashtags", styles)
    _append_paragraphs(story, " ".join(post.hashtags) if post.hashtags else "Sin hashtags", styles)
    _append_list_section(story, "Keywords utilizadas", post.keywords_used, styles, level=3)
    _append_list_section(story, "Evidencia utilizada", post.evidence_used, styles, level=3)
    _append_list_section(story, "Claims que requieren revisión", post.claims_requiring_review, styles, level=3)
    _append_list_section(story, "Notas", post.notes, styles, level=3)


def _append_heading(story: list[Any], text: str, styles: dict[str, ParagraphStyle], *, level: int) -> None:
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(_escape(text), styles["Heading1" if level == 1 else "Heading2"]))


def _append_label(story: list[Any], text: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph(_escape(text), styles["Label"]))


def _append_paragraphs(story: list[Any], text: str, styles: dict[str, ParagraphStyle]) -> None:
    for block in [value.strip() for value in str(text or "").splitlines() if value.strip()]:
        story.append(Paragraph(_escape(block), styles["Body"]))


def _append_list_section(
    story: list[Any],
    title: str,
    values: list[object],
    styles: dict[str, ParagraphStyle],
    *,
    level: int = 2,
) -> None:
    _append_heading(story, title, styles, level=1 if level <= 2 else 2)
    items = [str(value).strip() for value in values if str(value).strip()] or ["Sin elementos."]
    for item in items:
        story.append(Paragraph(f"- {_escape(item)}", styles["Bullet"]))


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "EditorialPlanTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_LEFT,
            textColor="#000000",
            spaceAfter=6,
        ),
        "Heading1": ParagraphStyle(
            "EditorialPlanHeading1",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            alignment=TA_LEFT,
            textColor="#000000",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "Heading2": ParagraphStyle(
            "EditorialPlanHeading2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            alignment=TA_LEFT,
            textColor="#000000",
            spaceBefore=6,
            spaceAfter=3,
        ),
        "Label": ParagraphStyle(
            "EditorialPlanLabel",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            spaceBefore=4,
            spaceAfter=1,
        ),
        "Body": ParagraphStyle(
            "EditorialPlanBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            spaceAfter=3,
        ),
        "Bullet": ParagraphStyle(
            "EditorialPlanBullet",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            leftIndent=10,
            firstLineIndent=-7,
            spaceAfter=2,
        ),
        "Small": ParagraphStyle(
            "EditorialPlanSmall",
            parent=sample["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            spaceAfter=2,
        ),
    }


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


def _day_order(post: LinkedInPostPlan) -> int:
    return {"monday": 0, "wednesday": 1, "friday": 2}.get(str(post.day), 99)


def _day_label(value: object) -> str:
    labels = {
        "monday": "Lunes",
        "wednesday": "Miércoles",
        "friday": "Viernes",
    }
    return labels.get(str(value), str(value))
