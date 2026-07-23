from __future__ import annotations

from services.application_communication_edit_validation_service import (
    apply_application_communication_edit_state,
    build_application_communication_edit_state,
    edit_state_changed,
)
from tests.application_communication_helpers import build_application_communication_kit


def test_edit_state_round_trip_preserves_original_when_unchanged():
    kit = build_application_communication_kit(1)
    state = build_application_communication_edit_state(kit)

    edited = apply_application_communication_edit_state(kit, state)

    assert edited == kit
    assert not edit_state_changed(kit, state)


def test_edit_state_applies_subject_and_message_updates():
    kit = build_application_communication_kit(1)
    state = build_application_communication_edit_state(kit)
    state["recruiter_message"] = state["recruiter_message"] + " Gracias por revisar mi perfil."
    state["subject_options"] = ["Postulación a Project Manager con experiencia Agile"]

    edited = apply_application_communication_edit_state(kit, state)

    assert "Gracias por revisar" in edited.recruiter_message.message
    assert edited.application_email.subject_options == ["Postulación a Project Manager con experiencia Agile"]
    assert edit_state_changed(kit, state)
