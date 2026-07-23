from __future__ import annotations

import json
import zipfile
from io import BytesIO

from exporters.final_package_exporter import FinalPackageExporter
from tests.final_package_helpers import build_package, fake_banner_bytes


def test_zip_export_contains_expected_structure_manifest_readme_json_and_banner():
    package = build_package(banner=True)
    data = FinalPackageExporter().export_zip(package, banner_image_bytes=fake_banner_bytes())

    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())
        root = "astrogato-vector-paquete-profesional/"
        assert root + "README.txt" in names
        assert root + "manifest.json" in names
        assert root + "linkedin-profile.md" in names
        assert root + "linkedin-profile.html" in names
        assert root + "linkedin-profile.docx" in names
        assert root + "linkedin-profile.pdf" in names
        assert root + "linkedin-banner.png" in names
        assert root + "data/compatibility-summary.json" in names
        assert root + "data/audit-summary.json" in names
        manifest = json.loads(archive.read(root + "manifest.json").decode("utf-8"))
        assert manifest["banner_included"] is True
        assert manifest["content_source"] == "generated-and-audited"
        assert "linkedin_score" in manifest
        compatibility = json.loads(archive.read(root + "data/compatibility-summary.json").decode("utf-8"))
        audit = json.loads(archive.read(root + "data/audit-summary.json").decode("utf-8"))
        assert compatibility[0]["score"] >= 0
        assert "quick_wins" in audit
        assert all(".." not in name for name in names)


def test_zip_export_omits_banner_when_absent():
    data = FinalPackageExporter().export_zip(build_package(banner=False))

    with zipfile.ZipFile(BytesIO(data)) as archive:
        assert "astrogato-vector-paquete-profesional/linkedin-banner.png" not in archive.namelist()
