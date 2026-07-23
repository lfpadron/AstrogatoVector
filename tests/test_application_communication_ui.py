from __future__ import annotations

from streamlit.testing.v1 import AppTest

from services.application_communication_audit_service import audit_application_communication_kit
from services.application_communication_edit_validation_service import build_application_communication_edit_state
from services.communication_redundancy_audit_service import audit_communication_redundancy
from services.targeted_cv_audit_service import audit_targeted_cv
from tests.application_communication_helpers import (
    build_application_communication_inputs,
    build_application_communication_kit,
)
from utils.session import SessionKeys


def test_application_communication_tab_shows_summary_editor_and_download_actions():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)
    job = market.job_analyses[0]
    job_compatibility = compatibility.job_compatibilities[0]
    cv = targeted_cvs[1]
    cv_audit = audit_targeted_cv(cv, profile, job, job_compatibility)
    audit = audit_application_communication_kit(kit, profile, job, job_compatibility, cv)
    redundancy = audit_communication_redundancy(kit, cv)
    edit_state = build_application_communication_edit_state(kit)
    edit_state["_source_fingerprint"] = "fp-comm-1"

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "compatibility_payload": compatibility.model_dump(),
            "cv_payload": cv.model_dump(),
            "cv_audit_payload": cv_audit.model_dump(),
            "kit_payload": kit.model_dump(),
            "audit_payload": audit.model_dump(),
            "redundancy_payload": redundancy.model_dump(),
            "edit_state": edit_state,
        },
    )

    at.run(timeout=10)

    page_text = _page_text(at)
    button_labels = [button.label for button in at.button]
    assert "Kit de postulación por vacante" in page_text
    assert "Kits generados" in page_text
    assert any("Vacante 1" in expander.label and "Project Manager" in expander.label for expander in at.expander)
    assert "Generar kits para todas las vacantes" in button_labels
    assert "Validar cambios" in button_labels
    assert "Carta de presentación" in [item.label for item in at.text_area]
    assert "Mensaje para recruiter" in [item.label for item in at.text_area]


def _render_results_with_state(
    profile_payload=None,
    market_payload=None,
    compatibility_payload=None,
    cv_payload=None,
    cv_audit_payload=None,
    kit_payload=None,
    audit_payload=None,
    redundancy_payload=None,
    edit_state=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_application_communication_ui_test_seeded"):
        st.session_state["_application_communication_ui_test_seeded"] = True
        st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        st.session_state[SessionKeys.COMPATIBILITY_REPORT] = compatibility_payload
        st.session_state[SessionKeys.TARGETED_CVS] = {"1": cv_payload}
        st.session_state[SessionKeys.TARGETED_CV_AUDITS] = {"1": cv_audit_payload}
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_KITS] = {"1": kit_payload}
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_AUDITS] = {"1": audit_payload}
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS] = {"1": redundancy_payload}
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS] = {"1": "fp-comm-1"}
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES] = {"1": edit_state}
    render_results()


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    values.extend(str(metric.label) for metric in getattr(at, "metric", []))
    return "\n".join(values)
