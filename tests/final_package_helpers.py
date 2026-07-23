from __future__ import annotations

from io import BytesIO

from PIL import Image

from exporters.final_package_exporter import FinalPackageExporter
from schemas.deliverable_models import FinalDeliverablePackage
from schemas.enums import OutputLanguage
from schemas.examples import (
    build_example_audit_report,
    build_example_compatibility_report,
    build_example_linkedin_profile,
    build_example_market_analysis,
    build_example_professional_profile,
)
from services.final_package_service import FinalPackageService


def build_package(*, language: OutputLanguage | str = OutputLanguage.ES, banner: bool = False) -> FinalDeliverablePackage:
    result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        build_example_linkedin_profile(),
        build_example_compatibility_report(),
        build_example_audit_report(),
        language,
        banner_available=banner,
        banner_fingerprint="test-banner" if banner else None,
    )
    assert result.success
    assert result.package is not None
    return result.package


def build_edited_package() -> FinalDeliverablePackage:
    linkedin = build_example_linkedin_profile()
    edit_state = {
        "edited": True,
        "banner": {
            "primary_line": "Project Manager editada",
            "specialty_line": "Producto digital y métricas",
            "supporting_line": "Coordinación ejecutiva",
            "visual_concept": linkedin.banner.visual_concept,
            "recommended_template": linkedin.banner.recommended_template,
        },
        "headline": "Project Manager editada | Producto digital y métricas",
        "about": linkedin.about.text,
        "experience": [
            {
                "suggested_role_title": "Project Manager editada",
                "rewritten_text": linkedin.experience[0].rewritten_text,
            }
        ],
        "selected_skills": ["Gestión de proyectos"],
        "selected_keywords": ["Stakeholder management"],
    }
    result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        linkedin,
        build_example_compatibility_report(),
        build_example_audit_report(),
        OutputLanguage.ES,
        edit_state=edit_state,
    )
    assert result.success
    assert result.package is not None
    return result.package


def fake_banner_bytes() -> bytes:
    image = Image.new("RGB", (1584, 396), "#14365c")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def build_exports(package: FinalDeliverablePackage | None = None, *, banner: bool = False) -> dict[str, bytes]:
    package = package or build_package(banner=banner)
    banner_bytes = fake_banner_bytes() if banner else None
    exporter = FinalPackageExporter()
    return {
        "markdown": exporter.export_markdown(package),
        "html": exporter.export_html(package, banner_image_bytes=banner_bytes),
        "docx": exporter.export_docx(package, banner_image_bytes=banner_bytes),
        "pdf": exporter.export_pdf(package, banner_image_bytes=banner_bytes),
        "zip": exporter.export_zip(package, banner_image_bytes=banner_bytes),
    }
