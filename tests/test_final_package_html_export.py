from __future__ import annotations

from exporters.final_package_exporter import FinalPackageExporter
from tests.final_package_helpers import build_package, fake_banner_bytes


def test_html_export_is_local_accessible_and_self_contained_for_individual_download():
    html = FinalPackageExporter().export_html(
        build_package(banner=True),
        banner_image_bytes=fake_banner_bytes(),
        embed_banner=True,
    ).decode("utf-8")

    lowered = html.casefold()
    assert "<!doctype html>" in lowered
    assert 'charset="utf-8"' in lowered
    assert "<style>" in lowered
    assert "<script" not in lowered
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "data:image/png;base64" in lowered
    assert "@media print" in lowered


def test_html_export_uses_relative_banner_for_zip_mode():
    html = FinalPackageExporter().export_html(
        build_package(banner=True),
        banner_image_bytes=fake_banner_bytes(),
        embed_banner=False,
    ).decode("utf-8")

    assert 'src="linkedin-banner.png"' in html
    assert "data:image/png" not in html
