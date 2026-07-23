from __future__ import annotations

from services.application_communication_service import build_application_communication_input_fingerprint
from tests.application_communication_helpers import build_application_communication_inputs


def test_fingerprint_changes_when_targeted_cv_changes():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    cv = targeted_cvs[1]
    base = build_application_communication_input_fingerprint(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        cv,
        "es",
        model_name="quality-model",
    )
    changed_cv = cv.model_copy(update={"ats_keywords_used": [*cv.ats_keywords_used, "Nueva keyword"]})
    changed = build_application_communication_input_fingerprint(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        changed_cv,
        "es",
        model_name="quality-model",
    )

    assert base != changed
