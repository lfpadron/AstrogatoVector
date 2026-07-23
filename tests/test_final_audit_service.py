from __future__ import annotations

from schemas.audit_models import (
    ATS_AUDIT_COMPONENT_WEIGHTS,
    LINKEDIN_AUDIT_COMPONENT_WEIGHTS,
    AuditRecommendation,
)
from schemas.profile_models import HeadlineOutput
from services.compatibility_scoring_service import CompatibilityScoringService
from services.final_audit_service import FinalAuditService, build_final_audit_fingerprint
from services.final_audit_validation_service import audit_final_report
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import build_candidate_profile, build_linkedin_output, build_market_analysis


def test_final_audit_generates_explainable_scores_and_findings():
    profile, market, linkedin, compatibility = _audit_inputs()

    report = FinalAuditService().generate_report(profile, market, linkedin, compatibility)

    assert report.success
    assert report.audit_passed
    assert report.linkedin_positioning is not None
    assert report.ats_estimation is not None
    assert report.overall_score == round((report.linkedin_positioning.score + report.ats_estimation.score) / 2, 1)
    assert {component.name for component in report.linkedin_positioning.components} == set(LINKEDIN_AUDIT_COMPONENT_WEIGHTS)
    assert {component.name for component in report.ats_estimation.components} == set(ATS_AUDIT_COMPONENT_WEIGHTS)
    assert all(finding.title and finding.impact and finding.recommendation for finding in report.findings)
    assert all(finding.category in {"About", "Experience", "Skills", "ATS", "Keywords", "Market Alignment"} for finding in report.findings)


def test_final_audit_prioritizes_quick_win_for_missing_headline_keyword():
    profile, market, linkedin, compatibility = _audit_inputs()
    headline = HeadlineOutput(
        text="Project Manager para iniciativas digitales",
        character_count=0,
        included_keywords=[],
    )
    linkedin = linkedin.model_copy(update={"headline": headline})

    report = FinalAuditService().generate_report(profile, market, linkedin, compatibility)

    assert report.success
    assert any(finding.title == "Keyword principal ausente" for finding in report.findings)
    assert any(action.priority == "Quick Wins" and action.category == "Headline" for action in report.quick_wins)


def test_final_audit_fingerprint_changes_when_linkedin_profile_changes():
    profile, market, linkedin, compatibility = _audit_inputs()
    first = build_final_audit_fingerprint(profile, market, linkedin, compatibility)
    linkedin = linkedin.model_copy(
        update={
            "headline": HeadlineOutput(
                text="Project Manager con enfoque en ejecución digital",
                character_count=0,
                included_keywords=[],
            )
        }
    )

    second = build_final_audit_fingerprint(profile, market, linkedin, compatibility)

    assert first != second


def test_final_audit_local_validation_flags_non_actionable_recommendation():
    profile, market, linkedin, compatibility = _audit_inputs()
    report = FinalAuditService().generate_report(profile, market, linkedin, compatibility)
    bad_recommendation = AuditRecommendation(
        priority="Quick Wins",
        category="Headline",
        title="Recomendación genérica",
        action="Mejora tu perfil",
        rationale="No es accionable.",
        evidence=[],
    )
    report = report.model_copy(update={"recommendations": [bad_recommendation]})

    validation = audit_final_report(report)

    assert not validation.passed
    assert any("acción recomendada" in finding.message for finding in validation.findings)


def _audit_inputs():
    profile = build_candidate_profile()
    market = build_market_analysis()
    linkedin = build_linkedin_output()
    _, _, evaluation = build_compatibility_inputs()
    compatibility = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    return profile, market, linkedin, compatibility
