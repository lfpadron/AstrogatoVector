from __future__ import annotations

from streamlit.testing.v1 import AppTest

from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from services.compatibility_scoring_service import CompatibilityScoringService
from tests.compatibility_helpers import build_compatibility_inputs
from utils.session import SessionKeys


def test_compatibility_view_shows_scores_dimensions_gaps_and_methodology():
    profile, market, evaluation = build_compatibility_inputs()
    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    result = CompatibilityAnalysisResult(
        success=True,
        semantic_evaluation=evaluation,
        compatibility_report=report,
        model_used="quality-model",
        input_tokens=300,
        output_tokens=200,
        total_tokens=500,
        latency_ms=450,
        audit_passed=True,
        prompt_version="1.0",
        methodology_version="1.0",
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "result_payload": result.model_dump(),
            "report_payload": report.model_dump(),
        },
    )
    at.run(timeout=10)

    page_text = _page_text(at)
    table_text = _table_text(at)
    assert "Compatibilidad con vacantes" in page_text
    assert "No son probabilidades de contratación" in page_text
    assert "Vacante 1" in page_text
    assert "Score promedio" in page_text
    assert "Kubernetes" in page_text
    assert "¿Cómo se calcula el score?" in [expander.label for expander in at.expander]
    assert "Herramientas y tecnologías" in table_text
    assert "Detalles del análisis de compatibilidad" in [expander.label for expander in at.expander]
    download_labels = [button.label for button in getattr(at, "download_button", [])]
    assert "Descargar mercado objetivo (.md)" in download_labels
    assert "Descargar compatibilidad (.md)" in download_labels
    assert "unit-test-secret" not in page_text
    assert "Devuelve únicamente" not in page_text


def test_reprocess_compatibility_failure_preserves_previous_report(monkeypatch):
    profile, market, evaluation = build_compatibility_inputs()
    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    previous = CompatibilityAnalysisResult(
        success=True,
        semantic_evaluation=evaluation,
        compatibility_report=report,
        model_used="quality-model",
        audit_passed=True,
        prompt_version="1.0",
        methodology_version="1.0",
    )
    calls = {"count": 0}

    def fake_reprocess(*args, **kwargs):
        calls["count"] += 1
        return CompatibilityAnalysisResult(
            success=False,
            model_used="quality-model",
            error_category="timeout_error",
            user_message="La solicitud tardó más de lo permitido.",
            retryable=True,
        )

    monkeypatch.setattr("components.result_views.run_compatibility_from_session", fake_reprocess)
    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": profile.model_dump(),
            "market_payload": market.model_dump(),
            "result_payload": previous.model_dump(),
            "report_payload": report.model_dump(),
        },
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Reprocesar compatibilidad").click()
    at.run(timeout=10)

    assert calls["count"] == 1
    assert at.session_state[SessionKeys.COMPATIBILITY_REPORT] is not None
    assert "compatibilidad" in at.session_state[SessionKeys.PROCESS_ERROR]


def _render_results_with_state(profile_payload=None, market_payload=None, result_payload=None, report_payload=None):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_compatibility_ui_test_seeded"):
        st.session_state["_compatibility_ui_test_seeded"] = True
        if profile_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        if market_payload is not None:
            st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        if result_payload is not None:
            st.session_state[SessionKeys.COMPATIBILITY_ANALYSIS_RESULT] = result_payload
        if report_payload is not None:
            st.session_state[SessionKeys.COMPATIBILITY_REPORT] = report_payload
    render_results()


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    return "\n".join(values)


def _table_text(at: AppTest) -> str:
    return "\n".join(str(table.value) for table in at.table)
