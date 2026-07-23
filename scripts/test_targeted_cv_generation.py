"""Smoke test for targeted CV generation, audits and exports with fictitious data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exporters.targeted_cv_docx_exporter import TargetedCVDocxExporter  # noqa: E402
from exporters.targeted_cv_markdown_exporter import TargetedCVMarkdownExporter  # noqa: E402
from exporters.targeted_cv_pdf_exporter import TargetedCVPDFExporter  # noqa: E402
from exporters.targeted_cv_zip_exporter import TARGETED_CV_ZIP_FILENAME, TargetedCVZipExporter  # noqa: E402
from services.export_audit_service import ExportAuditService  # noqa: E402
from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402
from services.targeted_cv_ats_audit_service import audit_targeted_cv_ats  # noqa: E402
from services.targeted_cv_audit_service import audit_targeted_cv  # noqa: E402
from services.targeted_cv_generation_service import TargetedCVGenerationService  # noqa: E402
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-preview", action="store_true")
    parser.add_argument("--openai", action="store_true", help="Use the configured OpenAI model instead of fake local CVs.")
    args = parser.parse_args()

    profile, market, compatibility = build_targeted_cv_inputs()
    cvs = []
    generation_summaries = []
    if args.openai:
        try:
            service = TargetedCVGenerationService(create_openai_service())
        except OpenAIConfigurationError:
            print("targeted_cv_openai=configuration_incomplete")
            return 0
        for job in market.job_analyses:
            job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == job.job_index)
            result = service.generate_targeted_cv(profile, job, job_compatibility, "es")
            generation_summaries.append(
                {
                    "job_index": job.job_index,
                    "success": result.success,
                    "category": result.error_category,
                    "retryable": result.retryable,
                    "model": result.model_used,
                }
            )
            if result.success and result.targeted_cv is not None:
                cvs.append(result.targeted_cv)
    else:
        for job in market.job_analyses:
            cvs.append(build_targeted_cv(job.job_index))
            generation_summaries.append({"job_index": job.job_index, "success": True, "category": "fake_local"})

    audits = {}
    ats_audits = {}
    for cv in cvs:
        job = next(item for item in market.job_analyses if item.job_index == cv.target_job_index)
        job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == cv.target_job_index)
        audits[cv.target_job_index] = audit_targeted_cv(cv, profile, job, job_compatibility)
        ats_audits[cv.target_job_index] = audit_targeted_cv_ats(cv, profile, job, job_compatibility)

    print("generation=" + json.dumps(generation_summaries, ensure_ascii=False, sort_keys=True))
    print("audit_passed=" + json.dumps({index: audit.passed for index, audit in audits.items()}, sort_keys=True))
    print("ats_scores=" + json.dumps({index: audit.overall_score for index, audit in ats_audits.items()}, sort_keys=True))

    if not cvs or not all(audit.passed for audit in audits.values()):
        print("targeted_cv_generation=failed_or_audit_blocked")
        return 1

    markdown_exporter = TargetedCVMarkdownExporter()
    docx_exporter = TargetedCVDocxExporter()
    pdf_exporter = TargetedCVPDFExporter()
    zip_bytes = TargetedCVZipExporter().export(cvs, audits=audits, ats_audits=ats_audits)
    export_audit = ExportAuditService().audit_targeted_cv_zip(zip_bytes)
    files = {TARGETED_CV_ZIP_FILENAME: zip_bytes}
    for cv in cvs:
        prefix = f"vacancy-{cv.target_job_index:02d}"
        files[f"{prefix}-cv.md"] = markdown_exporter.export(cv)
        files[f"{prefix}-cv.docx"] = docx_exporter.export(cv)
        files[f"{prefix}-cv.pdf"] = pdf_exporter.export(cv)

    print(f"zip_export_audit_passed={export_audit.passed}")
    print("sizes=" + json.dumps({name: len(data) for name, data in files.items()}, indent=2, sort_keys=True))
    if not export_audit.passed:
        print("zip_findings=" + json.dumps(export_audit.findings, ensure_ascii=False))
        return 1

    if args.save_preview:
        output_dir = PROJECT_ROOT / "tmp" / "targeted_cv_preview"
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (output_dir / name).write_bytes(data)
        print(f"preview_saved={output_dir}")
    else:
        print("preview_saved=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
