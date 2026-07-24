"""Smoke test for editorial plan generation, audits and exports with fictitious data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exporters.editorial_plan_docx_exporter import EditorialPlanDocxExporter  # noqa: E402
from exporters.editorial_plan_html_exporter import EditorialPlanHTMLExporter  # noqa: E402
from exporters.editorial_plan_markdown_exporter import EditorialPlanMarkdownExporter  # noqa: E402
from exporters.editorial_plan_pdf_exporter import EditorialPlanPDFExporter  # noqa: E402
from exporters.editorial_plan_zip_exporter import EDITORIAL_PLAN_ZIP_FILENAME, EditorialPlanZipExporter  # noqa: E402
from services.editorial_plan_audit_service import audit_editorial_plan  # noqa: E402
from services.editorial_plan_service import EditorialPlanService  # noqa: E402
from services.export_audit_service import ExportAuditService  # noqa: E402
from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-preview", action="store_true")
    parser.add_argument("--openai", action="store_true", help="Use the configured OpenAI model instead of a fake local plan.")
    args = parser.parse_args()

    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    if args.openai:
        try:
            service = EditorialPlanService(create_openai_service())
        except OpenAIConfigurationError:
            print("editorial_plan_openai=configuration_incomplete")
            return 0
        result = service.generate_editorial_plan(profile, market, compatibility, audit_report, "es")
        print(
            "generation="
            + json.dumps(
                {
                    "success": result.success,
                    "category": result.error_category,
                    "retryable": result.retryable,
                    "model": result.model_used,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        if not result.success or result.professional_brand_plan is None:
            return 1
        plan = result.professional_brand_plan
    else:
        plan = build_editorial_plan()
        print("generation=" + json.dumps({"success": True, "category": "fake_local"}, sort_keys=True))

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)
    print(f"audit_passed={audit.passed}")
    print(f"post_count={len(plan.calendar.posts)}")
    print(f"week_count={len(plan.calendar.weeks)}")
    if not audit.passed:
        print("audit_findings=" + json.dumps([item.model_dump() for item in audit.findings], ensure_ascii=False))
        return 1

    files = {
        "linkedin-editorial-plan.md": EditorialPlanMarkdownExporter().export(plan),
        "linkedin-editorial-plan.html": EditorialPlanHTMLExporter().export(plan),
        "linkedin-editorial-plan.docx": EditorialPlanDocxExporter().export(plan),
        "linkedin-editorial-plan.pdf": EditorialPlanPDFExporter().export(plan),
        EDITORIAL_PLAN_ZIP_FILENAME: EditorialPlanZipExporter().export(plan),
    }
    export_audit = ExportAuditService().audit_editorial_plan_all(
        {
            "markdown": files["linkedin-editorial-plan.md"],
            "html": files["linkedin-editorial-plan.html"],
            "docx": files["linkedin-editorial-plan.docx"],
            "pdf": files["linkedin-editorial-plan.pdf"],
            "zip": files[EDITORIAL_PLAN_ZIP_FILENAME],
        }
    )
    print(f"export_audit_passed={export_audit.passed}")
    print("sizes=" + json.dumps({name: len(data) for name, data in files.items()}, indent=2, sort_keys=True))
    if not export_audit.passed:
        print("export_findings=" + json.dumps(export_audit.findings, ensure_ascii=False))
        return 1

    if args.save_preview:
        output_dir = PROJECT_ROOT / "tmp" / "editorial_plan_preview"
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (output_dir / name).write_bytes(data)
        print(f"preview_saved={output_dir}")
    else:
        print("preview_saved=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
