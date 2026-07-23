from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from exporters.targeted_cv_pdf_exporter import TargetedCVPDFExporter
from services.export_audit_service import ExportAuditService
from tests.targeted_cv_helpers import build_targeted_cv


def test_targeted_cv_pdf_export_has_selectable_text():
    data = TargetedCVPDFExporter().export(build_targeted_cv(1))
    reader = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert data.startswith(b"%PDF")
    assert "PERFIL PROFESIONAL" in text
    assert "EXPERIENCIA PROFESIONAL" in text
    assert "score" not in text.casefold()
    assert ExportAuditService().audit_targeted_cv_pdf(data).passed
