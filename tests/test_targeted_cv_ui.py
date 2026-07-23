from __future__ import annotations

from streamlit.testing.v1 import AppTest

from services.targeted_cv_ats_audit_service import audit_targeted_cv_ats
from services.targeted_cv_audit_service import audit_targeted_cv
from services.targeted_cv_edit_validation_service import build_targeted_cv_edit_state
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs
from utils.session import SessionKeys


def test_targeted_cv_tab_shows_summary_cards_and_editor():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)
    audit = audit_targeted_cv(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])
    ats = audit_targeted_cv_ats(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])
    edit_state = build_targeted_cv_edit_state(cv)
    edit_state["_source_fingerprint"] = "fp-1"

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "compatibility_payload": compatibility.model_dump(),
            "cv_payload": cv.model_dump(),
            "audit_payload": audit.model_dump(),
            "ats_payload": ats.model_dump(),
            "edit_state": edit_state,
        },
    )

    at.run(timeout=10)

    page_text = _page_text(at)
    button_labels = [button.label for button in at.button]
    assert "CV optimizado por vacante" in page_text
    assert "CVs generados" in page_text
    assert any("Vacante 1: Project Manager" in expander.label for expander in at.expander)
    assert "Generar CVs para todas las vacantes" in button_labels
    assert "Validar cambios del CV" in button_labels
    assert "Título profesional" in [item.label for item in at.text_input]


def _render_results_with_state(
    profile_payload=None,
    market_payload=None,
    compatibility_payload=None,
    cv_payload=None,
    audit_payload=None,
    ats_payload=None,
    edit_state=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_targeted_cv_ui_test_seeded"):
        st.session_state["_targeted_cv_ui_test_seeded"] = True
        st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        st.session_state[SessionKeys.COMPATIBILITY_REPORT] = compatibility_payload
        st.session_state[SessionKeys.TARGETED_CVS] = {"1": cv_payload}
        st.session_state[SessionKeys.TARGETED_CV_AUDITS] = {"1": audit_payload}
        st.session_state[SessionKeys.TARGETED_CV_ATS_AUDITS] = {"1": ats_payload}
        st.session_state[SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS] = {"1": "fp-1"}
        st.session_state[SessionKeys.TARGETED_CV_EDIT_STATES] = {"1": edit_state}
    render_results()


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    values.extend(str(metric.label) for metric in getattr(at, "metric", []))
    return "\n".join(values)
