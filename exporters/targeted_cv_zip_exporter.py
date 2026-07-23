"""ZIP exporter for all targeted CV deliverables."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from typing import Any

from schemas.targeted_cv_models import TargetedCV, TargetedCVATSAudit, TargetedCVAuditResult, TARGETED_CV_EXPORT_VERSION
from exporters.targeted_cv_docx_exporter import TargetedCVDocxExporter
from exporters.targeted_cv_markdown_exporter import TargetedCVMarkdownExporter
from exporters.targeted_cv_pdf_exporter import TargetedCVPDFExporter
from utils.filename_utils import safe_download_filename

TARGETED_CV_ZIP_FILENAME = safe_download_filename("astrogato-vector-cvs-por-vacante", "zip")
TARGETED_CV_ZIP_ROOT = "targeted-cvs"


class TargetedCVZipExporter:
    """Export all targeted CVs and review summaries into one ZIP."""

    def __init__(self) -> None:
        self._markdown = TargetedCVMarkdownExporter()
        self._docx = TargetedCVDocxExporter()
        self._pdf = TargetedCVPDFExporter()

    def export(
        self,
        targeted_cvs: list[TargetedCV],
        *,
        audits: dict[int, TargetedCVAuditResult] | None = None,
        ats_audits: dict[int, TargetedCVATSAudit] | None = None,
        edit_validations: dict[int, Any] | None = None,
    ) -> bytes:
        """Export ZIP bytes with one folder per target vacancy."""
        audits = audits or {}
        ats_audits = ats_audits or {}
        edit_validations = edit_validations or {}
        cvs = sorted(targeted_cvs, key=lambda item: item.target_job_index)
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{TARGETED_CV_ZIP_ROOT}/README.txt", _readme(cvs))
            archive.writestr(f"{TARGETED_CV_ZIP_ROOT}/manifest.json", _json_bytes(_manifest(cvs)))
            for cv in cvs:
                folder = f"{TARGETED_CV_ZIP_ROOT}/vacancy-{cv.target_job_index:02d}"
                archive.writestr(f"{folder}/cv.md", self._markdown.export(cv))
                archive.writestr(f"{folder}/cv.docx", self._docx.export(cv))
                archive.writestr(f"{folder}/cv.pdf", self._pdf.export(cv))
                archive.writestr(
                    f"{folder}/review-summary.json",
                    _json_bytes(_review_summary(cv, audits.get(cv.target_job_index), ats_audits.get(cv.target_job_index), edit_validations.get(cv.target_job_index))),
                )
        return output.getvalue()


def _manifest(cvs: list[TargetedCV]) -> dict[str, Any]:
    return {
        "export_version": TARGETED_CV_EXPORT_VERSION,
        "root": TARGETED_CV_ZIP_ROOT,
        "vacancy_count": len(cvs),
        "included_files": [
            f"vacancy-{cv.target_job_index:02d}/cv.{extension}"
            for cv in cvs
            for extension in ("md", "docx", "pdf")
        ]
        + [f"vacancy-{cv.target_job_index:02d}/review-summary.json" for cv in cvs],
        "vacancies": [
            {
                "job_index": cv.target_job_index,
                "job_title": cv.target_job_title,
                "company": cv.target_company,
                "content_source": cv.content_source,
            }
            for cv in cvs
        ],
        "privacy": {
            "original_cv_included": False,
            "raw_jobs_included": False,
            "prompts_included": False,
            "raw_model_responses_included": False,
        },
    }


def _review_summary(
    cv: TargetedCV,
    audit: TargetedCVAuditResult | None,
    ats_audit: TargetedCVATSAudit | None,
    edit_validation: Any | None,
) -> dict[str, Any]:
    validation_payload = edit_validation.model_dump(mode="json") if hasattr(edit_validation, "model_dump") else edit_validation
    return {
        "job_index": cv.target_job_index,
        "job_title": cv.target_job_title,
        "company": cv.target_company,
        "cv_version": cv.cv_version,
        "export_version": cv.export_version,
        "content_source": cv.content_source,
        "ats_score": ats_audit.overall_score if ats_audit else None,
        "ats_component_scores": ats_audit.component_scores if ats_audit else {},
        "audit_passed": audit.passed if audit else None,
        "audit_findings": audit.model_dump(mode="json")["findings"] if audit else [],
        "edit_validation": validation_payload or {},
        "review_note": "El CV debe revisarse por una persona antes de enviarse. El score no garantiza entrevistas ni contratación.",
    }


def _readme(cvs: list[TargetedCV]) -> bytes:
    lines = [
        "Astrogato Vector - CVs específicos por vacante",
        "",
        "Cada carpeta vacancy-XX contiene:",
        "- cv.md",
        "- cv.docx",
        "- cv.pdf",
        "- review-summary.json",
        "",
        "Los CVs no incluyen scores, brechas, evidencias internas ni prompts.",
        "Los archivos review-summary.json contienen información de revisión para uso del candidato.",
        "",
        f"Vacantes incluidas: {len(cvs)}",
    ]
    return "\n".join(lines).encode("utf-8")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
