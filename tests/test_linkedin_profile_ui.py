from __future__ import annotations

from streamlit.testing.v1 import AppTest

from schemas.enums import ContentSource, OutputLanguage
from schemas.extraction_models import CandidateExtractionResult
from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from schemas.input_models import CandidateInput, DocumentParseSummary, JobInput
from schemas.job_analysis_models import JobAnalysisResult
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from services.candidate_extraction_pipeline import CandidateExtractionRun
from services.compatibility_pipeline import CompatibilityAnalysisRun
from services.job_analysis_pipeline import JobAnalysisRun
from services.linkedin_profile_generation_pipeline import LinkedInProfileGenerationRun
from services.openai_service import STRUCTURED_OUTPUT_ERROR_MESSAGE
from services.compatibility_scoring_service import CompatibilityScoringService
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import build_candidate_profile, build_linkedin_output, build_market_analysis
from utils.session import SessionKeys


def test_linkedin_profile_view_shows_editable_sections_without_later_outputs():
    result = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
        prompt_version="1.0",
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "generation_result_payload": result.model_dump(),
            "profile_output_payload": build_linkedin_output().model_dump(),
        },
    )
    at.run(timeout=10)

    page_text = _page_text(at)
    table_text = _table_text(at)
    assert "Perfil de LinkedIn optimizado" in page_text
    assert "Banner profesional" in page_text
    assert "Headline" in page_text
    assert "About" in page_text
    assert "Experiencia reescrita" in page_text
    assert "Keywords ATS" in page_text
    assert "Revisión humana necesaria" in page_text
    assert any(selectbox.label == "Estilo visual" for selectbox in at.selectbox)
    assert "Generar banner PNG" in [button.label for button in at.button]
    assert "Agile" in table_text
    assert "Kubernetes" in table_text
    assert "probabilidades de contratación" in page_text
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in page_text
    assert "unit-test-secret" not in page_text


def test_linkedin_generation_failure_shows_safe_validation_details_without_output():
    result = LinkedInProfileGenerationResult(
        success=False,
        model_used="quality-model",
        error_category="pydantic_validation_error",
        user_message=STRUCTURED_OUTPUT_ERROR_MESSAGE,
        warnings=[
            "Detalle de validación estructurada: headline.character_count: "
            "Value error, character_count must match len(text) (value_error)."
        ],
        prompt_version="1.0",
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "candidate_profile_payload": build_candidate_profile().model_dump(),
            "market_payload": build_market_analysis().model_dump(),
            "generation_result_payload": result.model_dump(),
        },
    )
    at.run(timeout=10)

    page_text = _page_text(at)
    assert "Categoría técnica: pydantic_validation_error" in page_text
    assert "headline.character_count" in page_text
    assert "Resultado válido: No" in page_text
    assert "El perfil optimizado aparecerá aquí cuando la generación se complete correctamente." in page_text


def test_reprocess_generation_failure_preserves_existing_output(monkeypatch):
    calls = {"count": 0}

    def fake_reprocess(*args, **kwargs):
        calls["count"] += 1
        return LinkedInProfileGenerationResult(
            success=False,
            model_used="quality-model",
            error_category="timeout_error",
            user_message="La solicitud tardo mas de lo permitido.",
            retryable=True,
        )

    monkeypatch.setattr("components.result_views.run_linkedin_profile_generation_from_session", fake_reprocess)
    previous = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "candidate_profile_payload": build_candidate_profile().model_dump(),
            "market_payload": build_market_analysis().model_dump(),
            "generation_result_payload": previous.model_dump(),
            "profile_output_payload": build_linkedin_output().model_dump(),
            "validated_input_payload": _validated_input_payload(),
        },
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Reprocesar perfil de LinkedIn").click()
    at.run(timeout=10)

    assert calls["count"] == 1
    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] is not None
    assert "perfil de LinkedIn" in at.session_state[SessionKeys.PROCESS_ERROR]


def test_editing_generated_text_updates_edit_state_without_calling_model(monkeypatch):
    calls = {"count": 0}

    def fake_reprocess(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("No generation call expected while editing.")

    monkeypatch.setattr("components.result_views.run_linkedin_profile_generation_from_session", fake_reprocess)
    result = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "generation_result_payload": result.model_dump(),
            "profile_output_payload": build_linkedin_output().model_dump(),
        },
    )
    at.run(timeout=10)
    next(area for area in at.text_area if area.label == "Headline editable").set_value("Headline editado por usuario")
    at.run(timeout=10)

    assert calls["count"] == 0
    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE]["edited"] is True
    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT]["headline"]["text"] != "Headline editado por usuario"


def test_clear_removes_linkedin_profile_generation_state():
    result = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
    )
    at = AppTest.from_function(
        _render_results_with_clear,
        kwargs={
            "generation_result_payload": result.model_dump(),
            "profile_output_payload": build_linkedin_output().model_dump(),
            "banner_render_payload": {"success": True, "fingerprint": "banner-fingerprint"},
        },
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Limpiar").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] is None
    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] is None
    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] is None
    assert at.session_state[SessionKeys.BANNER_RENDER_RESULT] is None
    assert at.session_state[SessionKeys.BANNER_IMAGE_BYTES] is None
    assert at.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] is None


def test_process_runs_candidate_market_and_linkedin_generation_with_mocks(monkeypatch):
    calls = {"candidate": 0, "market": 0, "compatibility": 0, "linkedin": 0}

    def fake_candidate_pipeline(candidate_input, **kwargs):
        calls["candidate"] += 1
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=True,
                profile=build_candidate_profile(),
                model_used="quality-model",
                evidence_audit_passed=True,
            ),
            fingerprint="candidate-fingerprint",
            reused=False,
        )

    def fake_job_pipeline(jobs, output_language, **kwargs):
        calls["market"] += 1
        return JobAnalysisRun(
            result=JobAnalysisResult(
                success=True,
                market_analysis=build_market_analysis(),
                model_used="quality-model",
                audit_passed=True,
            ),
            fingerprint="jobs-fingerprint",
            reused=False,
        )

    def fake_linkedin_pipeline(candidate_profile, market_analysis, output_language, **kwargs):
        calls["linkedin"] += 1
        return LinkedInProfileGenerationRun(
            result=LinkedInProfileGenerationResult(
                success=True,
                profile_output=build_linkedin_output(),
                model_used="quality-model",
                audit_passed=True,
            ),
            fingerprint="linkedin-fingerprint",
            reused=False,
        )

    def fake_compatibility_pipeline(candidate_profile, market_analysis, output_language, **kwargs):
        calls["compatibility"] += 1
        profile, market, evaluation = build_compatibility_inputs()
        report = CompatibilityScoringService().calculate_report(evaluation, market, profile)
        return CompatibilityAnalysisRun(
            result=CompatibilityAnalysisResult(
                success=True,
                semantic_evaluation=evaluation,
                compatibility_report=report,
                model_used="quality-model",
                audit_passed=True,
                prompt_version="1.0",
                methodology_version="1.0",
            ),
            fingerprint="compatibility-fingerprint",
            reused=False,
        )

    monkeypatch.setattr("components.candidate_extraction_flow.run_candidate_extraction_pipeline", fake_candidate_pipeline)
    monkeypatch.setattr("components.job_analysis_flow.run_job_analysis_pipeline", fake_job_pipeline)
    monkeypatch.setattr("components.compatibility_flow.run_compatibility_pipeline", fake_compatibility_pipeline)
    monkeypatch.setattr("components.linkedin_profile_flow.run_linkedin_profile_generation_pipeline", fake_linkedin_pipeline)
    at = AppTest.from_file("app.py").run(timeout=10)
    _fill_valid_form(at)
    next(button for button in at.button if button.label == "Procesar").click()
    at.run(timeout=10)

    assert len(at.exception) == 0
    assert calls == {"candidate": 1, "market": 1, "compatibility": 1, "linkedin": 1}
    assert at.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] is not None
    assert at.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] is not None
    assert at.session_state[SessionKeys.COMPATIBILITY_REPORT] is not None
    assert at.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] is not None
    assert at.session_state[SessionKeys.FINAL_AUDIT_REPORT] is not None
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in str(at.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT])


def _render_results_with_state(
    candidate_profile_payload=None,
    market_payload=None,
    generation_result_payload=None,
    profile_output_payload=None,
    validated_input_payload=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_linkedin_ui_test_seeded"):
        st.session_state["_linkedin_ui_test_seeded"] = True
        if candidate_profile_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = candidate_profile_payload
        if market_payload is not None:
            st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        if generation_result_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] = generation_result_payload
        if profile_output_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = profile_output_payload
        if validated_input_payload is not None:
            st.session_state[SessionKeys.VALIDATED_INPUT] = validated_input_payload
    render_results()


def _render_results_with_clear(generation_result_payload=None, profile_output_payload=None, banner_render_payload=None):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, consume_clear_request, initialize_session_state, request_clear_session_state

    initialize_session_state()
    if not st.session_state.get("_linkedin_ui_test_seeded"):
        st.session_state["_linkedin_ui_test_seeded"] = True
        if generation_result_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] = generation_result_payload
        if profile_output_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = profile_output_payload
        if banner_render_payload is not None:
            st.session_state[SessionKeys.BANNER_RENDER_RESULT] = banner_render_payload
            st.session_state[SessionKeys.BANNER_IMAGE_BYTES] = b"png"
            st.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] = "banner-fingerprint"
            st.session_state[SessionKeys.BANNER_LAST_RENDER] = "2026-07-22T12:00:00"
    st.button("Limpiar", on_click=request_clear_session_state)
    consume_clear_request()
    render_results()


def _fill_valid_form(at: AppTest) -> None:
    long_cv = (
        "CV_COMPLETO_NO_DEBE_MOSTRARSE Project Manager con Agile, Jira y stakeholder management. "
        "Gestiono proyectos, stakeholders y redujo tiempos de seguimiento 15%. "
        "Experiencia profesional en tecnologia y comunicacion operativa con equipos. "
    )
    long_job = "Vacante ficticia Project Manager con Agile, Jira, stakeholders y Kubernetes como brecha. " * 3
    at.checkbox[0].check()
    at.text_area[0].set_value(long_cv)
    at.text_input[1].set_value("Project Manager")
    at.text_area[2].set_value(long_job)
    at.text_input[4].set_value("Program Manager")
    at.text_area[3].set_value(long_job)


def _validated_input_payload() -> dict:
    cv_text = "Project Manager con Agile, Jira y stakeholder management. " * 4
    candidate_input = CandidateInput(
        cv_text=cv_text,
        cv_source=ContentSource.TEXT,
        cv_parse_summary=DocumentParseSummary(
            source=ContentSource.TEXT,
            character_count=len(cv_text),
            word_count=len(cv_text.split()),
        ),
        linkedin_text=None,
        linkedin_source=ContentSource.GENERATED,
        output_language=OutputLanguage.ES,
        jobs=[
            JobInput(index=1, title="Project Manager", description="Vacante ficticia Agile Jira. " * 5, source=ContentSource.TEXT),
            JobInput(index=2, title="Program Manager", description="Vacante ficticia stakeholders. " * 5, source=ContentSource.TEXT),
        ],
    )
    return candidate_input.model_dump()


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    return "\n".join(values)


def _table_text(at: AppTest) -> str:
    return "\n".join(str(table.value) for table in at.table)
