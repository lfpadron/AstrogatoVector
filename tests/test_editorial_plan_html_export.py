from __future__ import annotations

from exporters.editorial_plan_html_exporter import EditorialPlanHTMLExporter
from services.export_audit_service import ExportAuditService
from tests.editorial_plan_helpers import build_editorial_plan


def test_editorial_plan_html_export_is_standalone_and_audited():
    data = EditorialPlanHTMLExporter().export(build_editorial_plan())

    audit = ExportAuditService().audit_editorial_plan_html(data)

    assert audit.passed is True
    assert b"<script" not in data.lower()
