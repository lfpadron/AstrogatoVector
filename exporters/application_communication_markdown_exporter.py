"""Markdown exporter for application communication kits."""

from __future__ import annotations

from schemas.application_communication_models import ApplicationCommunicationKit
from utils.filename_utils import safe_download_filename

APPLICATION_COMMUNICATION_MARKDOWN_FILENAME_TEMPLATE = "postulacion-vacante-{index:02d}.md"


class ApplicationCommunicationMarkdownExporter:
    """Export one application communication kit to Markdown bytes."""

    def export(self, kit: ApplicationCommunicationKit) -> bytes:
        return application_communication_to_markdown(kit).encode("utf-8")


def application_communication_to_markdown(kit: ApplicationCommunicationKit) -> str:
    """Render a communication kit without prompts, raw metadata or full evidence."""
    lines = [
        f"# Kit de postulación - Vacante {kit.target_job_index:02d}",
        "",
        "## Contexto breve",
        "",
        f"- Cargo objetivo: {kit.target_job_title}",
        f"- Empresa: {kit.target_company or 'No especificada'}",
        "- Revisión humana requerida antes de enviar.",
        "",
        "## Carta de presentación",
        "",
        kit.cover_letter.full_text,
        "",
        "## Mensaje para recruiter",
        "",
        kit.recruiter_message.message,
        "",
        "## Asuntos sugeridos",
        "",
        *[f"{index}. {subject}" for index, subject in enumerate(kit.application_email.subject_options, start=1)],
        "",
        "## Correo de postulación",
        "",
        kit.application_email.full_text,
        "",
        "## Notas de revisión",
        "",
        *_bullets(_review_notes(kit)),
        "",
        "## Disclaimer",
        "",
        "Contenido orientativo generado desde evidencia estructurada. Revísalo antes de usarlo en una postulación real.",
    ]
    return "\n".join(lines).strip() + "\n"


def application_communication_download_filename(kit: ApplicationCommunicationKit, extension: str) -> str:
    """Return a safe individual download filename for one communication kit."""
    title = kit.target_job_title or f"vacante-{kit.target_job_index:02d}"
    return safe_download_filename(f"postulacion-vacante-{kit.target_job_index:02d}-{title}", extension)


def _review_notes(kit: ApplicationCommunicationKit) -> list[str]:
    notes = [
        *kit.personalization_notes,
        *kit.cover_letter.review_notes,
        *kit.recruiter_message.review_notes,
        *kit.application_email.review_notes,
        *kit.risks_or_claims_requiring_review,
    ]
    return notes or ["Verificar tono, datos de contacto y adjuntos antes de enviar."]


def _bullets(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values if str(value).strip()]
