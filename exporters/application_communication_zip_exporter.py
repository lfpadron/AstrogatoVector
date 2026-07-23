"""ZIP exporter for per-vacancy application communication kits."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any

from exporters.application_communication_docx_exporter import ApplicationCommunicationDocxExporter
from exporters.application_communication_markdown_exporter import ApplicationCommunicationMarkdownExporter
from exporters.application_communication_pdf_exporter import ApplicationCommunicationPDFExporter
from exporters.application_communication_txt_exporter import ApplicationCommunicationTxtExporter
from schemas.application_communication_models import (
    APPLICATION_COMMUNICATION_EXPORT_VERSION,
    APPLICATION_COMMUNICATION_VERSION,
    ApplicationCommunicationAuditResult,
    ApplicationCommunicationEditValidationResult,
    ApplicationCommunicationKit,
    CommunicationRedundancyAuditResult,
)
from schemas.compatibility_models import COMPATIBILITY_METHODOLOGY_VERSION
from schemas.targeted_cv_models import TARGETED_CV_ATS_METHODOLOGY_VERSION, TARGETED_CV_VERSION
from utils.filename_utils import safe_download_filename

APPLICATION_COMMUNICATION_ZIP_FILENAME = safe_download_filename(
    "astrogato-vector-comunicaciones-por-vacante",
    "zip",
)
APPLICATION_COMMUNICATION_ZIP_ROOT = "application-communications"


class ApplicationCommunicationZipExporter:
    """Export all application communication kits and reduced summaries into one ZIP."""

    def __init__(self) -> None:
        self._markdown = ApplicationCommunicationMarkdownExporter()
        self._txt = ApplicationCommunicationTxtExporter()
        self._docx = ApplicationCommunicationDocxExporter()
        self._pdf = ApplicationCommunicationPDFExporter()

    def export(
        self,
        kits: list[ApplicationCommunicationKit],
        *,
        audits: dict[int, ApplicationCommunicationAuditResult] | None = None,
        redundancy_audits: dict[int, CommunicationRedundancyAuditResult] | None = None,
        edit_validations: dict[int, ApplicationCommunicationEditValidationResult | dict[str, Any]] | None = None,
    ) -> bytes:
        """Export ZIP bytes with one folder per target vacancy."""
        audits = audits or {}
        redundancy_audits = redundancy_audits or {}
        edit_validations = edit_validations or {}
        ordered = sorted(kits, key=lambda item: item.target_job_index)
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{APPLICATION_COMMUNICATION_ZIP_ROOT}/README.txt", _readme(ordered))
            archive.writestr(f"{APPLICATION_COMMUNICATION_ZIP_ROOT}/manifest.json", _json_bytes(_manifest(ordered)))
            for kit in ordered:
                folder = f"{APPLICATION_COMMUNICATION_ZIP_ROOT}/vacancy-{kit.target_job_index:02d}"
                archive.writestr(f"{folder}/communication-kit.md", self._markdown.export(kit))
                archive.writestr(f"{folder}/communication-kit.txt", self._txt.export(kit))
                archive.writestr(f"{folder}/communication-kit.docx", self._docx.export(kit))
                archive.writestr(f"{folder}/communication-kit.pdf", self._pdf.export(kit))
                archive.writestr(
                    f"{folder}/review-summary.json",
                    _json_bytes(
                        _review_summary(
                            kit,
                            audits.get(kit.target_job_index),
                            redundancy_audits.get(kit.target_job_index),
                            edit_validations.get(kit.target_job_index),
                        )
                    ),
                )
        return output.getvalue()


def _manifest(kits: list[ApplicationCommunicationKit]) -> dict[str, Any]:
    files = [
        f"vacancy-{kit.target_job_index:02d}/communication-kit.{extension}"
        for kit in kits
        for extension in ("md", "txt", "docx", "pdf")
    ] + [f"vacancy-{kit.target_job_index:02d}/review-summary.json" for kit in kits]
    return {
        "package_version": APPLICATION_COMMUNICATION_EXPORT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": APPLICATION_COMMUNICATION_ZIP_ROOT,
        "output_language": _language(kits[0].output_language) if kits else None,
        "vacancy_count": len(kits),
        "generated_kit_count": len(kits),
        "files": files,
        "methodology_versions": {
            "compatibility": COMPATIBILITY_METHODOLOGY_VERSION,
            "targeted_cv": TARGETED_CV_VERSION,
            "targeted_cv_ats": TARGETED_CV_ATS_METHODOLOGY_VERSION,
            "communication": APPLICATION_COMMUNICATION_VERSION,
        },
        "privacy": {
            "original_cv_included": False,
            "raw_jobs_included": False,
            "full_evidence_included": False,
            "prompts_included": False,
            "raw_model_responses_included": False,
            "secrets_included": False,
        },
        "disclaimer": "Contenido orientativo. Requiere revisión humana antes de enviarse.",
    }


def _review_summary(
    kit: ApplicationCommunicationKit,
    audit: ApplicationCommunicationAuditResult | None,
    redundancy_audit: CommunicationRedundancyAuditResult | None,
    edit_validation: ApplicationCommunicationEditValidationResult | dict[str, Any] | None,
) -> dict[str, Any]:
    validation_payload = edit_validation.model_dump(mode="json") if hasattr(edit_validation, "model_dump") else edit_validation
    warning_values = []
    if audit:
        warning_values.extend(f"{item.path}: {item.message}" for item in audit.findings if item.severity == "warning")
    if redundancy_audit:
        warning_values.extend(
            f"{item.path}: {item.message}" for item in redundancy_audit.findings if item.severity == "warning"
        )
    return {
        "job_index": kit.target_job_index,
        "job_title": kit.target_job_title,
        "company": kit.target_company,
        "compatibility_score": kit.compatibility_score,
        "compatibility_band": kit.compatibility_band,
        "validation_status": {
            "communication_audit_passed": audit.passed if audit else None,
            "redundancy_audit_passed": redundancy_audit.passed if redundancy_audit else None,
            "edit_validation": validation_payload or {},
        },
        "word_counts": {
            "cover_letter": kit.cover_letter.word_count,
            "application_email": kit.application_email.word_count,
        },
        "character_counts": {
            "recruiter_message": kit.recruiter_message.character_count,
        },
        "strengths_used": sorted(
            {
                *kit.cover_letter.strengths_used,
                *kit.recruiter_message.strengths_used,
                *kit.application_email.strengths_used,
            }
        ),
        "gaps_not_claimed": kit.risks_or_claims_requiring_review,
        "warnings": warning_values,
        "suggested_subjects": kit.application_email.subject_options,
        "review_note": "El resumen no incluye el texto completo de carta, correo ni mensaje.",
    }


def _readme(kits: list[ApplicationCommunicationKit]) -> bytes:
    lines = [
        "Comunicaciones por vacante",
        "",
        "Cada carpeta vacancy-XX contiene:",
        "- communication-kit.md",
        "- communication-kit.txt",
        "- communication-kit.docx",
        "- communication-kit.pdf",
        "- review-summary.json",
        "",
        "Los archivos están pensados para revisión humana y copia manual.",
        "No se incluyen CVs originales, vacantes crudas, prompts, respuestas crudas, secretos ni evidencia completa.",
        "",
        f"Vacantes incluidas: {len(kits)}",
    ]
    return "\n".join(lines).encode("utf-8")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _language(value: object) -> str:
    return str(getattr(value, "value", value))
