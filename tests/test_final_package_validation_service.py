from __future__ import annotations

from schemas.profile_models import RewrittenExperienceEntry
from services.final_package_validation_service import validate_final_package
from tests.final_package_helpers import build_package


def test_final_package_validation_accepts_valid_package_with_banner_warning_only():
    package = build_package(banner=False)
    passed, findings, warnings = validate_final_package(package)

    assert passed
    assert findings == []
    assert "Banner PNG not included." in warnings


def test_final_package_validation_blocks_required_content_and_placeholders():
    package = build_package().model_copy(update={"headline": "", "about": "[TODO] Insert text"})
    passed, findings, _ = validate_final_package(package)

    assert not passed
    assert any("headline" in finding for finding in findings)
    assert any("placeholders" in finding for finding in findings)


def test_final_package_validation_blocks_unsupported_claims_sensitive_data_and_scores():
    package = build_package()
    experience = package.experiences[0].model_copy(update={"unsupported_claims": ["Claim sin respaldo"]})
    audit = package.audit_report.model_copy(update={"overall_score": 101})
    unsafe = package.model_copy(
        update={
            "experiences": [experience],
            "headline": "Project Manager con RFC ABCD010101XYZ",
            "audit_report": audit,
        }
    )
    passed, findings, _ = validate_final_package(unsafe)

    assert not passed
    assert any("unsupported_claims" in finding for finding in findings)
    assert any("dato sensible" in finding for finding in findings)
    assert any("scores" in finding for finding in findings)


def test_final_package_validation_blocks_empty_lists_and_missing_audit():
    package = build_package().model_copy(
        update={
            "experiences": [],
            "prioritized_skills": [],
            "ats_keywords": [],
            "audit_report": None,
        }
    )
    passed, findings, _ = validate_final_package(package)

    assert not passed
    assert any("experiencias" in finding for finding in findings)
    assert any("skills" in finding for finding in findings)
    assert any("keywords" in finding for finding in findings)
    assert any("auditoría" in finding for finding in findings)
