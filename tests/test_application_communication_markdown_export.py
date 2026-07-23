from __future__ import annotations

from exporters.application_communication_markdown_exporter import ApplicationCommunicationMarkdownExporter
from services.export_audit_service import ExportAuditService
from tests.application_communication_helpers import build_application_communication_kit


def test_markdown_export_contains_copy_sections_and_passes_audit():
    data = ApplicationCommunicationMarkdownExporter().export(build_application_communication_kit(1))
    text = data.decode("utf-8")

    assert "Carta de presentación" in text
    assert "Mensaje para recruiter" in text
    assert "Correo de postulación" in text
    assert "raw_response" not in text
    assert ExportAuditService().audit_application_communication_markdown(data).passed
