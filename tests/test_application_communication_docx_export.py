from __future__ import annotations

from io import BytesIO

from docx import Document

from exporters.application_communication_docx_exporter import ApplicationCommunicationDocxExporter
from services.export_audit_service import ExportAuditService
from tests.application_communication_helpers import build_application_communication_kit


def test_docx_export_opens_and_contains_three_pieces():
    data = ApplicationCommunicationDocxExporter().export(build_application_communication_kit(1))
    document = Document(BytesIO(data))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert "CARTA DE PRESENTACIÓN" in text
    assert "MENSAJE PARA RECRUITER" in text
    assert "CORREO DE POSTULACIÓN" in text
    assert len(document.inline_shapes) == 0
    assert ExportAuditService().audit_application_communication_docx(data).passed
