from __future__ import annotations

from exporters.final_package_exporter import FinalPackageExporter
from tests.final_package_helpers import build_package


def test_markdown_export_is_utf8_with_sections_tables_and_relative_banner():
    package = build_package(banner=True)
    text = FinalPackageExporter().export_markdown(package).decode("utf-8")

    assert text.startswith("# ")
    assert "## 2. Resumen ejecutivo" in text
    assert "| Rank | Skill | Categoría | Evidencia | Ubicación |" in text
    assert "![Banner de LinkedIn](linkedin-banner.png)" in text
    assert "<html" not in text.casefold()
    assert "Gestión" in text


def test_markdown_export_omits_banner_reference_when_absent_and_supports_english():
    package = build_package(language="en", banner=False)
    text = FinalPackageExporter().export_markdown(package).decode("utf-8")

    assert "Professional Positioning Package" in text
    assert "linkedin-banner.png" not in text
    assert "## 16. Metodología y disclaimer" in text
