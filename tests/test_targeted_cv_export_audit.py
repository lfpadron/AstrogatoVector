from __future__ import annotations

from services.export_audit_service import ExportAuditService


def test_targeted_cv_export_audit_rejects_internal_terms():
    data = (
        "# CV\n\n"
        "## Perfil profesional\n\nTexto con score interno.\n\n"
        "## Competencias clave\n\n- Agile\n\n"
        "## Experiencia profesional\n\n- Gestionó proyectos.\n"
    ).encode("utf-8")

    result = ExportAuditService().audit_targeted_cv_markdown(data)

    assert not result.passed
    assert any("score" in finding for finding in result.findings)
