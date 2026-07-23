from __future__ import annotations

from services.targeted_cv_generation_service import build_targeted_cv_input_fingerprint
from tests.targeted_cv_helpers import build_targeted_cv_inputs


def test_targeted_cv_fingerprint_changes_with_model_job_or_language():
    profile, market, compatibility = build_targeted_cv_inputs()
    base = build_targeted_cv_input_fingerprint(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "es",
        model_name="quality-model",
    )

    assert base != build_targeted_cv_input_fingerprint(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "en",
        model_name="quality-model",
    )
    assert base != build_targeted_cv_input_fingerprint(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "es",
        model_name="other-model",
    )
    assert base != build_targeted_cv_input_fingerprint(
        profile,
        market.job_analyses[1],
        compatibility.job_compatibilities[1],
        "es",
        model_name="quality-model",
    )
