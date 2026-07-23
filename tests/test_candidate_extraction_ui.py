from __future__ import annotations

from streamlit.testing.v1 import AppTest

from schemas.enums import EvidenceStatus, SeniorityLevel, SkillCategory
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.extraction_models import CandidateExtractionResult
from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from schemas.job_analysis_models import JobAnalysisResult
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis
from services.candidate_extraction_pipeline import CandidateExtractionRun
from services.job_analysis_pipeline import JobAnalysisRun
from services.compatibility_pipeline import CompatibilityAnalysisRun
from services.linkedin_profile_generation_pipeline import LinkedInProfileGenerationRun
from services.compatibility_scoring_service import CompatibilityScoringService
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import build_linkedin_output
from utils.session import SessionKeys


def test_results_view_shows_extracted_profile_and_evidence_without_raw_cv():
    result = CandidateExtractionResult(
        success=True,
        profile=_profile(),
        model_used="quality-model",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_ms=200,
        evidence_audit_passed=True,
        evidence_audit_findings=["warning: skills[0]: revisar inferencia"],
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={"result_payload": result.model_dump(), "profile_payload": _profile().model_dump()},
    )
    at.run(timeout=10)

    page_text = _page_text(at)
    assert "Perfil profesional extraído" in page_text
    assert "Project Manager" in page_text
    assert "Respaldado" in page_text
    assert any("Ver evidencia" in expander.label for expander in at.expander)
    assert "Responsable de coordinar proyectos" in page_text
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in page_text
    assert "unit-test-secret" not in page_text


def test_results_view_shows_audit_error_without_profile():
    result = CandidateExtractionResult(
        success=False,
        model_used="quality-model",
        error_category="evidence_audit_failed",
        user_message="La respuesta fue recibida, pero no superó la validación de evidencia.",
        evidence_audit_findings=["error: skills[0]: referencia inexistente"],
    )

    at = AppTest.from_function(_render_results_with_state, kwargs={"result_payload": result.model_dump()})
    at.run(timeout=10)

    page_text = _page_text(at)
    assert "no superó la validación de evidencia" in page_text
    assert "referencia inexistente" in page_text


def test_reprocess_failure_preserves_existing_profile(monkeypatch):
    def fake_pipeline(*args, **kwargs):
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=False,
                model_used="quality-model",
                error_category="timeout_error",
                user_message="La solicitud tardó más de lo permitido. Intenta nuevamente.",
                retryable=True,
            ),
            fingerprint="new-fingerprint",
            reused=False,
        )

    monkeypatch.setattr("components.candidate_extraction_flow.run_candidate_extraction_pipeline", fake_pipeline)
    previous_result = CandidateExtractionResult(
        success=True,
        profile=_profile(),
        model_used="quality-model",
        evidence_audit_passed=True,
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "result_payload": previous_result.model_dump(),
            "profile_payload": _profile().model_dump(),
            "validated_input_payload": _validated_input_payload(),
            "fingerprint": "old-fingerprint",
        },
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Reprocesar perfil").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] is not None
    page_text = _page_text(at)
    assert "Se conserva el último perfil profesional válido" in page_text


def test_process_calls_candidate_extraction_stage_with_mock(monkeypatch):
    calls = {"count": 0, "candidate_input": None}

    def fake_pipeline(candidate_input, **kwargs):
        calls["count"] += 1
        calls["candidate_input"] = candidate_input
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=True,
                profile=_profile(),
                model_used="quality-model",
                evidence_audit_passed=True,
            ),
            fingerprint="fingerprint",
            reused=False,
        )

    def fake_job_pipeline(jobs, output_language, **kwargs):
        return JobAnalysisRun(
            result=JobAnalysisResult(
                success=True,
                market_analysis=_market_analysis(),
                model_used="quality-model",
                audit_passed=True,
            ),
            fingerprint="jobs-fingerprint",
            reused=False,
        )

    def fake_linkedin_pipeline(candidate_profile, market_analysis, output_language, **kwargs):
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

    monkeypatch.setattr("components.candidate_extraction_flow.run_candidate_extraction_pipeline", fake_pipeline)
    monkeypatch.setattr("components.job_analysis_flow.run_job_analysis_pipeline", fake_job_pipeline)
    monkeypatch.setattr("components.compatibility_flow.run_compatibility_pipeline", fake_compatibility_pipeline)
    monkeypatch.setattr("components.linkedin_profile_flow.run_linkedin_profile_generation_pipeline", fake_linkedin_pipeline)
    at = AppTest.from_file("app.py").run(timeout=10)
    _fill_valid_form(at)
    next(button for button in at.button if button.label == "Procesar").click()
    at.run(timeout=10)

    assert len(at.exception) == 0
    assert calls["count"] == 1
    assert calls["candidate_input"] is not None
    payload = str(calls["candidate_input"].model_dump())
    assert "Responsabilidad exclusiva de vacante" in payload
    assert at.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] is not None


def test_clear_removes_candidate_extraction_state():
    result = CandidateExtractionResult(
        success=True,
        profile=_profile(),
        model_used="quality-model",
        evidence_audit_passed=True,
    )
    at = AppTest.from_function(
        _render_results_with_clear,
        kwargs={"result_payload": result.model_dump(), "profile_payload": _profile().model_dump()},
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Limpiar").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.CANDIDATE_EXTRACTION_RESULT] is None
    assert at.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] is None
    assert at.session_state[SessionKeys.CANDIDATE_EVIDENCE_AUDIT] is None


def _render_results_with_state(
    result_payload=None,
    profile_payload=None,
    validated_input_payload=None,
    fingerprint=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys
    from utils.session import initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_candidate_ui_test_seeded"):
        st.session_state["_candidate_ui_test_seeded"] = True
        if result_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_EXTRACTION_RESULT] = result_payload
        if profile_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        if validated_input_payload is not None:
            st.session_state[SessionKeys.VALIDATED_INPUT] = validated_input_payload
        if fingerprint is not None:
            st.session_state[SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT] = fingerprint
    render_results()


def _render_results_with_clear(result_payload=None, profile_payload=None):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state, request_clear_session_state, consume_clear_request

    initialize_session_state()
    if not st.session_state.get("_candidate_ui_test_seeded"):
        st.session_state["_candidate_ui_test_seeded"] = True
        if result_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_EXTRACTION_RESULT] = result_payload
        if profile_payload is not None:
            st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
    st.button("Limpiar", on_click=request_clear_session_state)
    consume_clear_request()
    render_results()


def _fill_valid_form(at: AppTest) -> None:
    long_cv = (
        "María Ejemplo Senior Project Manager en Empresa Demostración. "
        "Responsable de coordinar proyectos de transformación digital, gestionar riesgos y colaborar con equipos. "
        "Lideró la implementación de una nueva plataforma interna entregada dentro del calendario aprobado. "
        "Educación Maestría en Administración de Tecnologías. Idiomas Español nativo. Inglés intermedio. "
    )
    long_job = "Responsabilidad exclusiva de vacante para analizar mercado en otro incremento. " * 3
    at.checkbox[0].check()
    at.text_area[0].set_value(long_cv)
    at.text_input[1].set_value("Project Manager")
    at.text_area[2].set_value(long_job)
    at.text_input[4].set_value("Program Manager")
    at.text_area[3].set_value(long_job)


def _validated_input_payload() -> dict:
    from schemas.enums import ContentSource, OutputLanguage
    from schemas.input_models import CandidateInput, DocumentParseSummary, JobInput

    cv_text = "María Ejemplo Project Manager. Responsable de coordinar proyectos de transformación digital. " * 3
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
            JobInput(index=1, title="Project Manager", description="Vacante ficticia " * 10, source=ContentSource.TEXT),
            JobInput(index=2, title="Program Manager", description="Vacante ficticia " * 10, source=ContentSource.TEXT),
        ],
    )
    return candidate_input.model_dump()


def _profile() -> CandidateProfessionalProfile:
    reference = EvidenceReference(
        source_section="CV - Experiencia",
        source_excerpt="Responsable de coordinar proyectos de transformación digital",
    )
    skill = CandidateSkill(
        name="Gestión de proyectos",
        normalized_name="gestión de proyectos",
        category=SkillCategory.BUSINESS,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.9,
        years_experience=None,
        references=[reference],
    )
    responsibility = EvidenceItem(
        statement="Coordinó proyectos de transformación digital.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.88,
        references=[reference],
    )
    achievement = Achievement(
        description="Lideró la implementación de una nueva plataforma interna.",
        measurable_result=None,
        evidence_status=EvidenceStatus.SUPPORTED,
        references=[
            EvidenceReference(
                source_section="CV - Experiencia",
                source_excerpt="Lideró la implementación de una nueva plataforma interna",
            )
        ],
    )
    return CandidateProfessionalProfile(
        professional_identity="Project Manager",
        targetable_roles=["Project Manager"],
        summary="Project Manager con experiencia respaldada en transformación digital y gestión de riesgos.",
        total_years_experience=None,
        seniority=SeniorityLevel.MANAGER,
        industries=["Tecnología"],
        employment_history=[
            EmploymentEntry(
                employer="Empresa Demostración",
                role_title="Senior Project Manager",
                start_date="2018",
                end_date="2025",
                responsibilities=[responsibility],
                achievements=[achievement],
                technologies=[skill],
                industries=["Tecnología"],
            )
        ],
        skills=[skill],
        leadership_capabilities=[
            responsibility,
            EvidenceItem(
                statement="Posible liderazgo transversal por coordinación de equipos.",
                status=EvidenceStatus.INFERRED,
                category=SkillCategory.LEADERSHIP,
                confidence=0.7,
                references=[],
                notes="Inferencia para revisión humana.",
            ),
        ],
        education=[],
        certifications=[],
        languages=[],
        achievements=[achievement],
        ambiguities=["No se especifica tamaño de equipo."],
        conflicts=["No hay conflicto real; ejemplo visible para UI."],
        missing_information=["No hay cifras de presupuesto."],
    )


def _market_analysis() -> TargetMarketAnalysis:
    agile = JobRequirement(
        name="Agile",
        normalized_name="agile",
        category=SkillCategory.BUSINESS,
        description="Experiencia con Agile.",
        required=True,
        importance="high",
        exact_keywords=["Agile"],
    )
    return TargetMarketAnalysis(
        target_role_family="Gestion de proyectos",
        suggested_target_titles=["Project Manager", "Program Manager"],
        dominant_seniority=SeniorityLevel.MANAGER,
        market_summary="Mercado ficticio de gestion de proyectos con Agile.",
        common_responsibilities=["gestionar riesgos"],
        common_requirements=[agile],
        keywords=[
            MarketKeyword(
                keyword="Agile",
                normalized_keyword="agile",
                frequency=2,
                job_indices=[1, 2],
                category=SkillCategory.BUSINESS,
                priority="high",
            )
        ],
        business_skills=["gestion de riesgos"],
        job_analyses=[
            JobAnalysis(
                job_index=1,
                title="Project Manager",
                inferred_seniority=SeniorityLevel.MANAGER,
                role_summary="Rol para gestionar proyectos con Agile y riesgos.",
                responsibilities=["gestionar riesgos"],
                requirements=[agile],
                exact_keywords=["Agile"],
            ),
            JobAnalysis(
                job_index=2,
                title="Program Manager",
                inferred_seniority=SeniorityLevel.MANAGER,
                role_summary="Rol para coordinar programas con Agile y riesgos.",
                responsibilities=["gestionar riesgos"],
                requirements=[agile],
                exact_keywords=["Agile"],
            ),
        ],
    )


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    return "\n".join(values)
