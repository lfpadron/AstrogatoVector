from __future__ import annotations

from exporters.editorial_plan_pdf_exporter import EditorialPlanPDFExporter
from services.export_audit_service import ExportAuditService
from tests.editorial_plan_helpers import build_editorial_plan


def test_editorial_plan_pdf_export_has_selectable_text():
    data = EditorialPlanPDFExporter().export(build_editorial_plan())

    audit = ExportAuditService().audit_editorial_plan_pdf(data)

    assert audit.passed is True
    assert data.startswith(b"%PDF")
