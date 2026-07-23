from __future__ import annotations

from services.targeted_cv_edit_validation_service import (
    build_targeted_cv_edit_state,
    validate_targeted_cv_edits,
)
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def test_edit_validation_accepts_original_cv():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)
    edit_state = build_targeted_cv_edit_state(cv)

    result = validate_targeted_cv_edits(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0], edit_state)

    assert result.passed


def test_edit_validation_rejects_invented_metric():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)
    edit_state = build_targeted_cv_edit_state(cv)
    edit_state["experience"][0]["bullets"][0] = "Incrementó ingresos 99% sin evidencia."

    result = validate_targeted_cv_edits(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0], edit_state)

    assert not result.passed
    assert any("99%" in finding.message for finding in result.findings)
