from __future__ import annotations

from exporters.editorial_plan_docx_exporter import EditorialPlanDocxExporter
from services.export_audit_service import ExportAuditService
from tests.editorial_plan_helpers import build_editorial_plan


def test_editorial_plan_docx_export_opens_and_passes_audit():
    data = EditorialPlanDocxExporter().export(build_editorial_plan())

    audit = ExportAuditService().audit_editorial_plan_docx(data)

    assert audit.passed is True
    assert len(data) > 1000
