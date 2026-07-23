"""Smoke test for final package consolidation and export using fictitious data."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exporters.final_package_exporter import (  # noqa: E402
    FINAL_ZIP_FILENAME,
    INDIVIDUAL_DOCX_FILENAME,
    INDIVIDUAL_HTML_FILENAME,
    INDIVIDUAL_MARKDOWN_FILENAME,
    INDIVIDUAL_PDF_FILENAME,
    FinalPackageExporter,
)
from schemas.enums import OutputLanguage  # noqa: E402
from schemas.examples import (  # noqa: E402
    build_example_audit_report,
    build_example_compatibility_report,
    build_example_linkedin_profile,
    build_example_market_analysis,
    build_example_professional_profile,
)
from services.export_audit_service import ExportAuditService  # noqa: E402
from services.final_package_service import FinalPackageService  # noqa: E402


def main() -> None:
    """Run the final package export smoke test."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-preview", action="store_true")
    args = parser.parse_args()

    banner_bytes = _fake_banner_bytes()
    package_result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        build_example_linkedin_profile(),
        build_example_compatibility_report(),
        build_example_audit_report(),
        OutputLanguage.ES,
        banner_available=True,
        banner_fingerprint="fictitious-banner",
    )
    print(f"build_success={package_result.success}")
    print(f"validation_passed={package_result.validation_passed}")
    print(f"findings={package_result.findings}")
    print(f"warnings={package_result.warnings}")
    if not package_result.success or package_result.package is None:
        raise SystemExit(1)

    exporter = FinalPackageExporter()
    files = {
        INDIVIDUAL_MARKDOWN_FILENAME: exporter.export_markdown(package_result.package),
        INDIVIDUAL_HTML_FILENAME: exporter.export_html(package_result.package, banner_image_bytes=banner_bytes),
        INDIVIDUAL_DOCX_FILENAME: exporter.export_docx(package_result.package, banner_image_bytes=banner_bytes),
        INDIVIDUAL_PDF_FILENAME: exporter.export_pdf(package_result.package, banner_image_bytes=banner_bytes),
        FINAL_ZIP_FILENAME: exporter.export_zip(package_result.package, banner_image_bytes=banner_bytes),
    }
    audit = ExportAuditService().audit_all(
        {
            "markdown": files[INDIVIDUAL_MARKDOWN_FILENAME],
            "html": files[INDIVIDUAL_HTML_FILENAME],
            "docx": files[INDIVIDUAL_DOCX_FILENAME],
            "pdf": files[INDIVIDUAL_PDF_FILENAME],
            "zip": files[FINAL_ZIP_FILENAME],
        }
    )
    print(f"export_audit_passed={audit.passed}")
    print(f"export_findings={audit.findings}")
    print(f"export_warnings={audit.warnings}")
    print("sizes=" + json.dumps({name: len(data) for name, data in files.items()}, indent=2, sort_keys=True))
    with zipfile.ZipFile(BytesIO(files[FINAL_ZIP_FILENAME])) as archive:
        manifest = json.loads(
            archive.read("astrogato-vector-paquete-profesional/manifest.json").decode("utf-8")
        )
    print("manifest=" + json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    if not audit.passed:
        raise SystemExit(1)

    if args.save_preview:
        output_dir = PROJECT_ROOT / "tmp" / "final_package_preview"
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (output_dir / name).write_bytes(data)
        (output_dir / "linkedin-banner.png").write_bytes(banner_bytes)
        print(f"preview_saved={output_dir}")
    else:
        print("preview_saved=false")


def _fake_banner_bytes() -> bytes:
    image = Image.new("RGB", (1584, 396), "#14365c")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


if __name__ == "__main__":
    main()
