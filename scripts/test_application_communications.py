"""Smoke test for application communications, audits and exports with fictitious data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exporters.application_communication_docx_exporter import ApplicationCommunicationDocxExporter  # noqa: E402
from exporters.application_communication_markdown_exporter import ApplicationCommunicationMarkdownExporter  # noqa: E402
from exporters.application_communication_pdf_exporter import ApplicationCommunicationPDFExporter  # noqa: E402
from exporters.application_communication_txt_exporter import ApplicationCommunicationTxtExporter  # noqa: E402
from exporters.application_communication_zip_exporter import (  # noqa: E402
    APPLICATION_COMMUNICATION_ZIP_FILENAME,
    ApplicationCommunicationZipExporter,
)
from services.application_communication_audit_service import audit_application_communication_kit  # noqa: E402
from services.application_communication_service import ApplicationCommunicationService  # noqa: E402
from services.communication_redundancy_audit_service import audit_communication_redundancy  # noqa: E402
from services.export_audit_service import ExportAuditService  # noqa: E402
from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402
from tests.application_communication_helpers import (  # noqa: E402
    build_application_communication_inputs,
    build_application_communication_kit,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-preview", action="store_true")
    parser.add_argument("--openai", action="store_true", help="Use the configured OpenAI model instead of fake local kits.")
    args = parser.parse_args()

    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kits = []
    generation_summaries = []
    if args.openai:
        try:
            service = ApplicationCommunicationService(create_openai_service())
        except OpenAIConfigurationError:
            print("application_communications_openai=configuration_incomplete")
            return 0
        for job in market.job_analyses:
            job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == job.job_index)
            result = service.generate_communication_kit(profile, job, job_compatibility, targeted_cvs[job.job_index], "es")
            generation_summaries.append(
                {
                    "job_index": job.job_index,
                    "success": result.success,
                    "category": result.error_category,
                    "retryable": result.retryable,
                    "model": result.model_used,
                }
            )
            if result.success and result.communication_kit is not None:
                kits.append(result.communication_kit)
    else:
        for job in market.job_analyses:
            kits.append(build_application_communication_kit(job.job_index))
            generation_summaries.append({"job_index": job.job_index, "success": True, "category": "fake_local"})

    audits = {}
    redundancy_audits = {}
    for kit in kits:
        job = next(item for item in market.job_analyses if item.job_index == kit.target_job_index)
        job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == kit.target_job_index)
        targeted_cv = targeted_cvs[kit.target_job_index]
        audits[kit.target_job_index] = audit_application_communication_kit(
            kit,
            profile,
            job,
            job_compatibility,
            targeted_cv,
        )
        redundancy_audits[kit.target_job_index] = audit_communication_redundancy(kit, targeted_cv)

    print("generation=" + json.dumps(generation_summaries, ensure_ascii=False, sort_keys=True))
    print("audit_passed=" + json.dumps({index: audit.passed for index, audit in audits.items()}, sort_keys=True))
    print(
        "redundancy_passed="
        + json.dumps({index: audit.passed for index, audit in redundancy_audits.items()}, sort_keys=True)
    )

    if not kits or not all(audit.passed for audit in audits.values()) or not all(audit.passed for audit in redundancy_audits.values()):
        print("application_communications=failed_or_audit_blocked")
        return 1

    markdown_exporter = ApplicationCommunicationMarkdownExporter()
    txt_exporter = ApplicationCommunicationTxtExporter()
    docx_exporter = ApplicationCommunicationDocxExporter()
    pdf_exporter = ApplicationCommunicationPDFExporter()
    zip_bytes = ApplicationCommunicationZipExporter().export(
        kits,
        audits=audits,
        redundancy_audits=redundancy_audits,
    )
    export_audit = ExportAuditService().audit_application_communication_zip(zip_bytes)
    files = {APPLICATION_COMMUNICATION_ZIP_FILENAME: zip_bytes}
    for kit in kits:
        prefix = f"vacancy-{kit.target_job_index:02d}"
        files[f"{prefix}-communication-kit.md"] = markdown_exporter.export(kit)
        files[f"{prefix}-communication-kit.txt"] = txt_exporter.export(kit)
        files[f"{prefix}-communication-kit.docx"] = docx_exporter.export(kit)
        files[f"{prefix}-communication-kit.pdf"] = pdf_exporter.export(kit)

    print(f"zip_export_audit_passed={export_audit.passed}")
    print("sizes=" + json.dumps({name: len(data) for name, data in files.items()}, indent=2, sort_keys=True))
    if not export_audit.passed:
        print("zip_findings=" + json.dumps(export_audit.findings, ensure_ascii=False))
        return 1

    if args.save_preview:
        output_dir = PROJECT_ROOT / "tmp" / "application_communications_preview"
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (output_dir / name).write_bytes(data)
        print(f"preview_saved={output_dir}")
    else:
        print("preview_saved=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
