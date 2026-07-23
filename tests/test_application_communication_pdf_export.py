from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from exporters.application_communication_pdf_exporter import ApplicationCommunicationPDFExporter
from services.export_audit_service import ExportAuditService
from tests.application_communication_helpers import build_application_communication_kit


def test_pdf_export_has_selectable_text_and_sections():
    data = ApplicationCommunicationPDFExporter().export(build_application_communication_kit(1))
    reader = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert data.startswith(b"%PDF")
    assert "CARTA DE PRESENTACIÓN" in text
    assert "MENSAJE PARA RECRUITER" in text
    assert "CORREO DE POSTULACIÓN" in text
    assert ExportAuditService().audit_application_communication_pdf(data).passed
