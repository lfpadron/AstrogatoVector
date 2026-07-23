from __future__ import annotations

from services.compatibility_service import build_compatibility_analysis_fingerprint
from tests.compatibility_helpers import build_compatibility_inputs


def test_fingerprint_is_stable_for_same_reduced_inputs():
    profile, market, _ = build_compatibility_inputs()

    first = build_compatibility_analysis_fingerprint(profile, market, "es", model_name="quality-model")
    second = build_compatibility_analysis_fingerprint(profile, market, "es", model_name="quality-model")

    assert first == second


def test_fingerprint_changes_with_language_model_and_methodology():
    profile, market, _ = build_compatibility_inputs()

    base = build_compatibility_analysis_fingerprint(profile, market, "es", model_name="quality-model")

    assert build_compatibility_analysis_fingerprint(profile, market, "en", model_name="quality-model") != base
    assert build_compatibility_analysis_fingerprint(profile, market, "es", model_name="other-model") != base
    assert (
        build_compatibility_analysis_fingerprint(
            profile,
            market,
            "es",
            model_name="quality-model",
            methodology_version="2.0-test",
        )
        != base
    )


def test_fingerprint_changes_when_candidate_or_jobs_change():
    profile, market, _ = build_compatibility_inputs()
    base = build_compatibility_analysis_fingerprint(profile, market, "es", model_name="quality-model")

    profile.skills[0].name = "Agile delivery"
    changed_profile = build_compatibility_analysis_fingerprint(profile, market, "es", model_name="quality-model")
    market.job_analyses[0].tools_and_technologies.append("AWS")
    changed_market = build_compatibility_analysis_fingerprint(profile, market, "es", model_name="quality-model")

    assert changed_profile != base
    assert changed_market != changed_profile
