from __future__ import annotations

from streamlit.testing.v1 import AppTest

from services.compatibility_scoring_service import CompatibilityScoringService
from services.final_audit_service import FinalAuditService
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import build_candidate_profile, build_linkedin_output, build_market_analysis
from utils.session import SessionKeys


def test_final_audit_tab_shows_dashboard_findings_and_recommendations():
    profile, market, linkedin, compatibility, report = _audit_state()
    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "linkedin_payload": linkedin.model_dump(),
            "compatibility_payload": compatibility.model_dump(),
            "audit_payload": report.model_dump(),
        },
    )

    at.run(timeout=10)

    page_text = _page_text(at)
    table_text = _table_text(at)
    assert "Auditoría integral LinkedIn y ATS" in page_text
    assert "Resumen ejecutivo" in page_text
    assert "LinkedIn" in page_text
    assert "ATS" in page_text
    assert "Compatibilidad promedio" in page_text
    assert "Hallazgos" in page_text
    assert "Quick Wins" in page_text
    assert "Desglose de scores" in page_text
    assert "Cobertura keywords" in table_text
    assert "Resultado válido: Sí" in page_text


def test_final_audit_reprocess_button_uses_only_audit_stage(monkeypatch):
    profile, market, linkedin, compatibility, report = _audit_state()
    calls = {"count": 0}

    def fake_reaudit(*args, **kwargs):
        calls["count"] += 1
        return report

    monkeypatch.setattr("components.result_views.run_final_audit_from_session", fake_reaudit)
    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "linkedin_payload": linkedin.model_dump(),
            "compatibility_payload": compatibility.model_dump(),
            "audit_payload": report.model_dump(),
        },
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Reauditar").click()
    at.run(timeout=10)

    assert calls["count"] == 1
    assert at.session_state[SessionKeys.FINAL_AUDIT_REPORT] is not None
    assert "auditoría integral" in at.session_state[SessionKeys.PROCESS_MESSAGE]


def _audit_state():
    profile = build_candidate_profile()
    market = build_market_analysis()
    linkedin = build_linkedin_output()
    _, _, evaluation = build_compatibility_inputs()
    compatibility = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    report = FinalAuditService().generate_report(profile, market, linkedin, compatibility)
    return profile, market, linkedin, compatibility, report


def _render_results_with_state(
    profile_payload=None,
    market_payload=None,
    linkedin_payload=None,
    compatibility_payload=None,
    audit_payload=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_final_audit_ui_test_seeded"):
        st.session_state["_final_audit_ui_test_seeded"] = True
        if profile_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        if market_payload is not None:
            st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        if linkedin_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = linkedin_payload
        if compatibility_payload is not None:
            st.session_state[SessionKeys.COMPATIBILITY_REPORT] = compatibility_payload
        if audit_payload is not None:
            st.session_state[SessionKeys.FINAL_AUDIT_REPORT] = audit_payload
    render_results()


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    values.extend(str(metric.label) for metric in getattr(at, "metric", []))
    return "\n".join(values)


def _table_text(at: AppTest) -> str:
    return "\n".join(str(table.value) for table in at.table)
