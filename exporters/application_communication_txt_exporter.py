"""Plain text exporter for application communication kits."""

from __future__ import annotations

from schemas.application_communication_models import ApplicationCommunicationKit
from utils.filename_utils import safe_download_filename


class ApplicationCommunicationTxtExporter:
    """Export one application communication kit to UTF-8 plain text bytes."""

    def export(self, kit: ApplicationCommunicationKit) -> bytes:
        return application_communication_to_txt(kit).encode("utf-8")


def application_communication_to_txt(kit: ApplicationCommunicationKit) -> str:
    """Render copy/paste-friendly plain text."""
    lines = [
        "CARTA DE PRESENTACIÓN",
        "",
        kit.cover_letter.full_text,
        "",
        "MENSAJE PARA RECRUITER",
        "",
        kit.recruiter_message.message,
        "",
        "ASUNTOS SUGERIDOS",
        "",
        *[f"{index}. {subject}" for index, subject in enumerate(kit.application_email.subject_options, start=1)],
        "",
        "CORREO DE POSTULACIÓN",
        "",
        kit.application_email.full_text,
        "",
        "NOTAS DE REVISIÓN",
        "",
        *[f"- {note}" for note in _review_notes(kit)],
    ]
    return "\n".join(lines).strip() + "\n"


def application_communication_txt_download_filename(kit: ApplicationCommunicationKit) -> str:
    """Return a safe TXT download filename for one communication kit."""
    title = kit.target_job_title or f"vacante-{kit.target_job_index:02d}"
    return safe_download_filename(f"postulacion-vacante-{kit.target_job_index:02d}-{title}", "txt")


def _review_notes(kit: ApplicationCommunicationKit) -> list[str]:
    notes = [
        *kit.personalization_notes,
        *kit.cover_letter.review_notes,
        *kit.recruiter_message.review_notes,
        *kit.application_email.review_notes,
        *kit.risks_or_claims_requiring_review,
    ]
    return [note for note in notes if str(note).strip()] or ["Revisar antes de enviar."]
