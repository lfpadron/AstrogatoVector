"""ZIP exporter for LinkedIn professional editorial plans."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any

from exporters.editorial_plan_docx_exporter import EditorialPlanDocxExporter
from exporters.editorial_plan_html_exporter import EditorialPlanHTMLExporter
from exporters.editorial_plan_markdown_exporter import EditorialPlanMarkdownExporter, post_markdown, week_markdown
from exporters.editorial_plan_pdf_exporter import EditorialPlanPDFExporter
from schemas.audit_models import FINAL_AUDIT_METHODOLOGY_VERSION
from schemas.compatibility_models import COMPATIBILITY_METHODOLOGY_VERSION
from schemas.editorial_plan_models import EDITORIAL_PLAN_EXPORT_VERSION, EDITORIAL_PLAN_VERSION, ProfessionalBrandPlan
from utils.filename_utils import safe_download_filename

EDITORIAL_PLAN_ZIP_FILENAME = "linkedin-editorial-plan.zip"
EDITORIAL_PLAN_ZIP_ROOT = "linkedin-editorial-plan"


class EditorialPlanZipExporter:
    """Export the complete professional brand plan into one ZIP package."""

    def __init__(self) -> None:
        self._markdown = EditorialPlanMarkdownExporter()
        self._html = EditorialPlanHTMLExporter()
        self._docx = EditorialPlanDocxExporter()
        self._pdf = EditorialPlanPDFExporter()

    def export(self, plan: ProfessionalBrandPlan, *, edit_validation: object | None = None) -> bytes:
        """Return ZIP bytes with calendar files and per-week folders."""
        output = BytesIO()
        ordered_posts = sorted(plan.calendar.posts, key=lambda post: (post.week, _day_order(post.day)))
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{EDITORIAL_PLAN_ZIP_ROOT}/README.txt", _readme(plan))
            archive.writestr(f"{EDITORIAL_PLAN_ZIP_ROOT}/manifest.json", _json_bytes(_manifest(plan, edit_validation)))
            archive.writestr(f"{EDITORIAL_PLAN_ZIP_ROOT}/calendar.md", self._markdown.export(plan))
            archive.writestr(f"{EDITORIAL_PLAN_ZIP_ROOT}/calendar.html", self._html.export(plan))
            archive.writestr(f"{EDITORIAL_PLAN_ZIP_ROOT}/calendar.docx", self._docx.export(plan))
            archive.writestr(f"{EDITORIAL_PLAN_ZIP_ROOT}/calendar.pdf", self._pdf.export(plan))
            for week in range(1, 5):
                folder = f"{EDITORIAL_PLAN_ZIP_ROOT}/week{week:02d}"
                archive.writestr(f"{folder}/week{week:02d}.md", week_markdown(plan, week))
                for slot, post in enumerate([item for item in ordered_posts if item.week == week], start=1):
                    archive.writestr(f"{folder}/post{slot:02d}.md", post_markdown(post))
        return output.getvalue()


def editorial_plan_download_filename(extension: str) -> str:
    """Return a safe editorial plan filename for one extension."""
    if extension.casefold().strip(".") == "zip":
        return EDITORIAL_PLAN_ZIP_FILENAME
    return safe_download_filename("linkedin-editorial-plan", extension)


def _manifest(plan: ProfessionalBrandPlan, edit_validation: object | None) -> dict[str, Any]:
    validation_payload = edit_validation.model_dump(mode="json") if hasattr(edit_validation, "model_dump") else edit_validation
    return {
        "export_version": EDITORIAL_PLAN_EXPORT_VERSION,
        "plan_version": EDITORIAL_PLAN_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": EDITORIAL_PLAN_ZIP_ROOT,
        "output_language": str(getattr(plan.output_language, "value", plan.output_language)),
        "week_count": len(plan.calendar.weeks),
        "post_count": len(plan.calendar.posts),
        "files": [
            "calendar.md",
            "calendar.html",
            "calendar.docx",
            "calendar.pdf",
            *[
                f"week{week}/week{week}.md"
                for week in ("01", "02", "03", "04")
            ],
            *[
                f"week{post.week:02d}/post{slot:02d}.md"
                for post in sorted(plan.calendar.posts, key=lambda item: (item.week, _day_order(item.day)))
                for slot in [_slot_for_day(post.day)]
            ],
        ],
        "methodology_versions": {
            "compatibility": COMPATIBILITY_METHODOLOGY_VERSION,
            "audit": FINAL_AUDIT_METHODOLOGY_VERSION,
            "editorial_plan": EDITORIAL_PLAN_VERSION,
        },
        "privacy": {
            "original_cv_included": False,
            "raw_linkedin_included": False,
            "raw_jobs_included": False,
            "full_evidence_included": False,
            "prompts_included": False,
            "raw_model_responses_included": False,
            "images_included": False,
            "auto_publish_enabled": False,
        },
        "edit_validation": validation_payload or {},
        "disclaimer": "Borradores profesionales para revisión humana y publicación manual.",
    }


def _readme(plan: ProfessionalBrandPlan) -> bytes:
    lines = [
        "Plan editorial profesional de LinkedIn",
        "",
        "Contenido del paquete:",
        "- calendar.md",
        "- calendar.html",
        "- calendar.docx",
        "- calendar.pdf",
        "- week01, week02, week03, week04",
        "",
        "Cada carpeta semanal contiene un resumen de la semana y un archivo Markdown por publicación.",
        "No se incluyen CV original, LinkedIn original, vacantes completas, prompts, respuestas crudas, imágenes ni publicación automática.",
        "",
        f"Semanas: {len(plan.calendar.weeks)}",
        f"Publicaciones: {len(plan.calendar.posts)}",
    ]
    return "\n".join(lines).encode("utf-8")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _day_order(value: object) -> int:
    return {"monday": 0, "wednesday": 1, "friday": 2}.get(str(value), 99)


def _slot_for_day(value: object) -> int:
    return {"monday": 1, "wednesday": 2, "friday": 3}.get(str(value), 9)
