from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from exporters.final_package_exporter import FinalPackageExporter
from tests.final_package_helpers import build_package, fake_banner_bytes


def test_pdf_export_has_signature_pages_selectable_text_unicode_and_disclaimer():
    data = FinalPackageExporter().export_pdf(build_package(banner=True), banner_image_bytes=fake_banner_bytes())
    reader = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert data.startswith(b"%PDF")
    assert len(reader.pages) > 0
    assert "1. Portada" in text
    assert "16. Metodología y disclaimer" in text
    assert "Gestión" in text
    assert "scores no garantizan" in text


def test_pdf_export_works_without_banner():
    data = FinalPackageExporter().export_pdf(build_package(banner=False))
    reader = PdfReader(BytesIO(data))

    assert len(reader.pages) > 0
    assert len(data) > 1024
