from __future__ import annotations

from exporters.targeted_cv_markdown_exporter import TargetedCVMarkdownExporter
from services.export_audit_service import ExportAuditService
from tests.targeted_cv_helpers import build_targeted_cv


def test_targeted_cv_markdown_export_is_clean_and_audited():
    data = TargetedCVMarkdownExporter().export(build_targeted_cv(1))
    text = data.decode("utf-8")

    assert "# Project Manager" in text
    assert "## Perfil profesional" in text
    assert "## Experiencia profesional" in text
    assert "score" not in text.casefold()
    assert "auditoría" not in text.casefold()
    assert ExportAuditService().audit_targeted_cv_markdown(data).passed
