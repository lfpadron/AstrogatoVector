from __future__ import annotations

from services.application_communication_edit_validation_service import (
    build_application_communication_edit_state,
    validate_application_communication_edits,
)
from tests.application_communication_helpers import (
    build_application_communication_inputs,
    build_application_communication_kit,
)


def test_edit_validation_accepts_unchanged_valid_kit():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)
    state = build_application_communication_edit_state(kit)

    result = validate_application_communication_edits(
        kit,
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        state,
    )

    assert result.passed


def test_edit_validation_rejects_new_unsupported_number():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)
    state = build_application_communication_edit_state(kit)
    state["application_email_full_text"] = state["application_email_full_text"] + "\n\nLogré una mejora adicional de 99%."

    result = validate_application_communication_edits(
        kit,
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        state,
    )

    assert not result.passed
    assert any("99%" in finding.message for finding in result.findings)
