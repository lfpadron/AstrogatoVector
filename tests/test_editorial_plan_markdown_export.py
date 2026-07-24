from __future__ import annotations

from exporters.editorial_plan_markdown_exporter import EditorialPlanMarkdownExporter
from services.export_audit_service import ExportAuditService
from tests.editorial_plan_helpers import build_editorial_plan


def test_editorial_plan_markdown_export_passes_audit():
    data = EditorialPlanMarkdownExporter().export(build_editorial_plan())

    audit = ExportAuditService().audit_editorial_plan_markdown(data)

    assert audit.passed is True
    assert "Semana 4" in data.decode("utf-8")
