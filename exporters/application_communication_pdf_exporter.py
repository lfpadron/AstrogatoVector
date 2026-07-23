"""PDF exporter for application communication kits."""

from __future__ import annotations

import html
from io import BytesIO
from typing import Any

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from schemas.application_communication_models import ApplicationCommunicationKit


class ApplicationCommunicationPDFExporter:
    """Export one communication kit to selectable PDF bytes."""

    def export(self, kit: ApplicationCommunicationKit) -> bytes:
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=LETTER,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            title=f"Postulación vacante {kit.target_job_index:02d}",
        )
        styles = _styles()
        story: list[Any] = []
        story.append(Paragraph(_escape(f"Kit de postulación - Vacante {kit.target_job_index:02d}"), styles["Title"]))
        story.append(Paragraph(_escape(f"{kit.target_job_title} | {kit.target_company or 'Empresa no especificada'}"), styles["Body"]))
        _append_heading(story, "Carta de presentación", styles)
        _append_paragraphs(story, kit.cover_letter.full_text, styles)
        _append_heading(story, "Mensaje para recruiter", styles)
        _append_paragraphs(story, kit.recruiter_message.message, styles)
        _append_heading(story, "Asuntos sugeridos", styles)
        for subject in kit.application_email.subject_options:
            story.append(Paragraph(f"- {_escape(subject)}", styles["Bullet"]))
        _append_heading(story, "Correo de postulación", styles)
        _append_paragraphs(story, kit.application_email.full_text, styles)
        _append_heading(story, "Notas de revisión", styles)
        for note in _review_notes(kit):
            story.append(Paragraph(f"- {_escape(note)}", styles["Bullet"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph("Contenido orientativo; revisar antes de enviar.", styles["Small"]))
        doc.build(story)
        return output.getvalue()


def _append_heading(story: list[Any], title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(_escape(title.upper()), styles["Heading"]))


def _append_paragraphs(story: list[Any], text: str, styles: dict[str, ParagraphStyle]) -> None:
    for block in [value.strip() for value in text.splitlines() if value.strip()]:
        story.append(Paragraph(_escape(block), styles["Body"]))


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "ApplicationCommunicationTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_LEFT,
            textColor="#000000",
            spaceAfter=6,
        ),
        "Heading": ParagraphStyle(
            "ApplicationCommunicationHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
            textColor="#000000",
            spaceBefore=5,
            spaceAfter=3,
        ),
        "Body": ParagraphStyle(
            "ApplicationCommunicationBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=4,
        ),
        "Bullet": ParagraphStyle(
            "ApplicationCommunicationBullet",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            leftIndent=10,
            firstLineIndent=-7,
            spaceAfter=2,
        ),
        "Small": ParagraphStyle(
            "ApplicationCommunicationSmall",
            parent=sample["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=10.5,
            spaceAfter=2,
        ),
    }


def _review_notes(kit: ApplicationCommunicationKit) -> list[str]:
    notes = [
        *kit.personalization_notes,
        *kit.cover_letter.review_notes,
        *kit.recruiter_message.review_notes,
        *kit.application_email.review_notes,
        *kit.risks_or_claims_requiring_review,
    ]
    return [note for note in notes if str(note).strip()] or ["Revisar datos, tono y adjuntos antes de enviar."]


def _escape(value: str) -> str:
    return html.escape(value or "")
