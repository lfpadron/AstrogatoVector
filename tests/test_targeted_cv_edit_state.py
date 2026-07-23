from __future__ import annotations

from services.targeted_cv_edit_validation_service import (
    apply_targeted_cv_edit_state,
    build_targeted_cv_edit_state,
)
from tests.targeted_cv_helpers import build_targeted_cv


def test_edit_state_round_trip_without_changes_keeps_generated_source():
    cv = build_targeted_cv(1)
    edit_state = build_targeted_cv_edit_state(cv)

    edited = apply_targeted_cv_edit_state(cv, edit_state)

    assert edited.content_source == "generated-and-audited"
    assert edited.summary.text == cv.summary.text
    assert len(edited.skills) == len(cv.skills)


def test_edit_state_filters_selected_skills_and_marks_user_edited():
    cv = build_targeted_cv(1)
    edit_state = build_targeted_cv_edit_state(cv)
    edit_state["selected_skills"] = ["Agile"]

    edited = apply_targeted_cv_edit_state(cv, edit_state)

    assert edited.content_source == "user-edited"
    assert [skill.name for skill in edited.skills] == ["Agile"]
