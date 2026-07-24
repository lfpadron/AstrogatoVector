from __future__ import annotations

import io
import zipfile

from exporters.editorial_plan_zip_exporter import EDITORIAL_PLAN_ZIP_FILENAME, EditorialPlanZipExporter
from services.export_audit_service import ExportAuditService
from tests.editorial_plan_helpers import build_editorial_plan


def test_editorial_plan_zip_contains_required_calendar_and_week_files():
    data = EditorialPlanZipExporter().export(build_editorial_plan())

    audit = ExportAuditService().audit_editorial_plan_zip(data)

    assert EDITORIAL_PLAN_ZIP_FILENAME == "linkedin-editorial-plan.zip"
    assert audit.passed is True
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        names = set(archive.namelist())
    assert "linkedin-editorial-plan/calendar.md" in names
    assert "linkedin-editorial-plan/week04/post03.md" in names
