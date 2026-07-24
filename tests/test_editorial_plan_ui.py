from __future__ import annotations

from streamlit.testing.v1 import AppTest

from services.editorial_plan_audit_service import audit_editorial_plan
from services.editorial_plan_edit_validation_service import build_editorial_plan_edit_state
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs
from utils.session import SessionKeys


def test_editorial_plan_tab_shows_calendar_editor_and_download_actions():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = build_editorial_plan()
    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)
    edit_state = build_editorial_plan_edit_state(plan)
    edit_state["_source_fingerprint"] = "fp-editorial"

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "compatibility_payload": compatibility.model_dump(),
            "audit_report_payload": audit_report.model_dump(),
            "plan_payload": plan.model_dump(),
            "audit_payload": audit.model_dump(),
            "edit_state": edit_state,
        },
    )

    at.run(timeout=10)

    page_text = _page_text(at)
    button_labels = [button.label for button in at.button]
    text_area_labels = [item.label for item in at.text_area]
    assert "Marca Profesional" in page_text
    assert "Calendario" in page_text
    assert "linkedin-editorial-plan.md" in page_text
    assert "Regenerar plan editorial" in button_labels
    assert "Preparar descargas" in button_labels
    assert "Copiar texto" in button_labels
    assert "Hook" in text_area_labels
    assert "CTA" in text_area_labels


def _render_results_with_state(
    profile_payload=None,
    market_payload=None,
    compatibility_payload=None,
    audit_report_payload=None,
    plan_payload=None,
    audit_payload=None,
    edit_state=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_editorial_plan_ui_test_seeded"):
        st.session_state["_editorial_plan_ui_test_seeded"] = True
        st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        st.session_state[SessionKeys.COMPATIBILITY_REPORT] = compatibility_payload
        st.session_state[SessionKeys.FINAL_AUDIT_REPORT] = audit_report_payload
        st.session_state[SessionKeys.PROFESSIONAL_BRAND_PLAN] = plan_payload
        st.session_state[SessionKeys.EDITORIAL_PLAN_AUDIT] = audit_payload
        st.session_state[SessionKeys.EDITORIAL_PLAN_INPUT_FINGERPRINT] = "fp-editorial"
        st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_STATE] = edit_state
    render_results()


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    values.extend(str(metric.label) for metric in getattr(at, "metric", []))
    values.extend(str(table.value) for table in at.table)
    return "\n".join(values)
