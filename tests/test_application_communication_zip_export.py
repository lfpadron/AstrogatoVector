from __future__ import annotations

import json
import zipfile
from io import BytesIO

from exporters.application_communication_zip_exporter import ApplicationCommunicationZipExporter
from services.application_communication_audit_service import audit_application_communication_kit
from services.communication_redundancy_audit_service import audit_communication_redundancy
from services.export_audit_service import ExportAuditService
from tests.application_communication_helpers import (
    build_application_communication_inputs,
    build_application_communication_kit,
)


def test_zip_export_contains_required_structure_and_safe_summary():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kits = [build_application_communication_kit(1), build_application_communication_kit(2)]
    audits = {}
    redundancy = {}
    for kit in kits:
        job = next(item for item in market.job_analyses if item.job_index == kit.target_job_index)
        job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == kit.target_job_index)
        audits[kit.target_job_index] = audit_application_communication_kit(
            kit,
            profile,
            job,
            job_compatibility,
            targeted_cvs[kit.target_job_index],
        )
        redundancy[kit.target_job_index] = audit_communication_redundancy(kit, targeted_cvs[kit.target_job_index])

    data = ApplicationCommunicationZipExporter().export(kits, audits=audits, redundancy_audits=redundancy)

    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())
        summary = json.loads(archive.read("application-communications/vacancy-01/review-summary.json"))
    assert "application-communications/README.txt" in names
    assert "application-communications/manifest.json" in names
    assert "application-communications/vacancy-01/communication-kit.md" in names
    assert "application-communications/vacancy-01/communication-kit.txt" in names
    assert "application-communications/vacancy-01/communication-kit.docx" in names
    assert "application-communications/vacancy-01/communication-kit.pdf" in names
    assert "application-communications/vacancy-01/review-summary.json" in names
    assert "cover_letter" in summary["word_counts"]
    assert "full_text" not in summary
    assert ExportAuditService().audit_application_communication_zip(data).passed
