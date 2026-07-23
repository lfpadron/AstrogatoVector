from __future__ import annotations

from exporters.application_communication_txt_exporter import ApplicationCommunicationTxtExporter
from services.export_audit_service import ExportAuditService
from tests.application_communication_helpers import build_application_communication_kit


def test_txt_export_is_copy_paste_friendly_and_passes_audit():
    data = ApplicationCommunicationTxtExporter().export(build_application_communication_kit(1))
    text = data.decode("utf-8")

    assert "CARTA DE PRESENTACIÓN" in text
    assert "MENSAJE PARA RECRUITER" in text
    assert "ASUNTOS SUGERIDOS" in text
    assert "CORREO DE POSTULACIÓN" in text
    assert ExportAuditService().audit_application_communication_txt(data).passed
