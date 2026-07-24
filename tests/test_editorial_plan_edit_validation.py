from __future__ import annotations

from services.editorial_plan_edit_validation_service import (
    build_editorial_plan_edit_state,
    editorial_plan_edit_state_changed,
    validate_editorial_plan_edits,
)
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs


def test_editorial_plan_edit_state_and_validation_are_local():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = build_editorial_plan()
    edit_state = build_editorial_plan_edit_state(plan)
    edit_state["posts"][0]["body"] = "Texto demasiado breve."

    validation = validate_editorial_plan_edits(plan, profile, market, compatibility, audit_report, edit_state)

    assert editorial_plan_edit_state_changed(plan, edit_state) is True
    assert validation.passed is False
    assert validation.findings
