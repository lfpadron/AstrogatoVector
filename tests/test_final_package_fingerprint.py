from __future__ import annotations

from services.final_package_service import build_final_package_fingerprint
from tests.final_package_helpers import build_package


def test_final_package_fingerprint_changes_with_language_and_banner():
    package = build_package()
    english = build_package(language="en")

    first = build_final_package_fingerprint(package, banner_available=False)
    second = build_final_package_fingerprint(english, banner_available=False)
    with_banner = build_final_package_fingerprint(package, banner_available=True, banner_fingerprint="banner")

    assert first != second
    assert first != with_banner


def test_final_package_fingerprint_changes_with_editable_content():
    package = build_package()
    edited = package.model_copy(update={"headline": "Headline diferente y validado"})

    assert build_final_package_fingerprint(package) != build_final_package_fingerprint(edited)
