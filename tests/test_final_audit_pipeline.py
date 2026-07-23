from __future__ import annotations

from services.compatibility_scoring_service import CompatibilityScoringService
from services.final_audit_pipeline import SESSION_REUSE_MESSAGE, run_final_audit_pipeline
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import build_candidate_profile, build_linkedin_output, build_market_analysis


def test_final_audit_pipeline_reuses_successful_report_with_same_fingerprint():
    profile = build_candidate_profile()
    market = build_market_analysis()
    linkedin = build_linkedin_output()
    _, _, evaluation = build_compatibility_inputs()
    compatibility = CompatibilityScoringService().calculate_report(evaluation, market, profile)

    first = run_final_audit_pipeline(profile, market, linkedin, compatibility)
    second = run_final_audit_pipeline(
        profile,
        market,
        linkedin,
        compatibility,
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
    )

    assert first.result.success
    assert second.reused
    assert second.fingerprint == first.fingerprint
    assert SESSION_REUSE_MESSAGE in second.result.warnings


def test_final_audit_pipeline_force_recomputes():
    profile = build_candidate_profile()
    market = build_market_analysis()
    linkedin = build_linkedin_output()
    _, _, evaluation = build_compatibility_inputs()
    compatibility = CompatibilityScoringService().calculate_report(evaluation, market, profile)

    first = run_final_audit_pipeline(profile, market, linkedin, compatibility)
    second = run_final_audit_pipeline(
        profile,
        market,
        linkedin,
        compatibility,
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        force=True,
    )

    assert first.fingerprint == second.fingerprint
    assert not second.reused
    assert second.result.success
