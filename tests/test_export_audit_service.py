from __future__ import annotations

import zipfile
from io import BytesIO

from services.export_audit_service import ExportAuditService
from tests.final_package_helpers import build_exports


def test_export_audit_accepts_valid_exports():
    exports = build_exports(banner=True)
    result = ExportAuditService().audit_all(exports)

    assert result.passed
    assert result.findings == []


def test_export_audit_rejects_invalid_html_and_unsafe_zip_path():
    service = ExportAuditService()
    html_result = service.audit_html(b"<html><script src='http://x'></script></html>")
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("../evil.txt", b"bad")

    zip_result = service.audit_zip(zip_buffer.getvalue())

    assert not html_result.passed
    assert any("scripts" in finding for finding in html_result.findings)
    assert not zip_result.passed
    assert any("ruta insegura" in finding for finding in zip_result.findings)
