from __future__ import annotations

from streamlit.testing.v1 import AppTest

from schemas.enums import ContentSource, EvidenceStatus, OutputLanguage, SeniorityLevel, SkillCategory
from schemas.evidence_models import (
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.extraction_models import CandidateExtractionResult
from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from schemas.input_models import CandidateInput, DocumentParseSummary, JobInput
from schemas.job_analysis_models import JobAnalysisResult
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis
from services.candidate_extraction_pipeline import CandidateExtractionRun
from services.compatibility_pipeline import CompatibilityAnalysisRun
from services.job_analysis_pipeline import JobAnalysisRun
from services.linkedin_profile_generation_pipeline import LinkedInProfileGenerationRun
from services.compatibility_scoring_service import CompatibilityScoringService
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import build_linkedin_output
from utils.session import SessionKeys


def test_market_view_shows_analysis_without_candidate_claims_or_raw_sources():
    result = JobAnalysisResult(
        success=True,
        market_analysis=_market_analysis(),
        model_used="quality-model",
        input_tokens=100,
        output_tokens=80,
        total_tokens=180,
        latency_ms=250,
        request_id="req-market",
        audit_passed=True,
        warnings=["Descripcion de vacante truncada para mantener limites seguros."],
        prompt_version="1.0",
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "job_result_payload": result.model_dump(),
            "market_payload": _market_analysis().model_dump(),
        },
    )
    at.run(timeout=10)

    page_text = _page_text(at)
    table_text = _table_text(at)
    assert "Mercado objetivo" in page_text
    assert "No implica que el candidato posea todas estas competencias" in page_text
    assert "Gestion de proyectos" in page_text
    assert "Agile" in table_text
    assert any("Vacante 1" in expander.label for expander in at.expander)
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in page_text
    assert "LinkedIn SECRETO" not in page_text
    assert "DESCRIPCION_RAW_SECRETA" not in page_text
    assert "Headline" not in page_text
    assert "About" not in page_text


def test_market_view_shows_audit_error_without_market_analysis():
    result = JobAnalysisResult(
        success=False,
        model_used="quality-model",
        error_category="job_analysis_audit_failed",
        user_message="La respuesta fue recibida, pero no supero la auditoria de vacantes.",
        audit_findings=["error: keywords[0]: keyword no aparece en las vacantes recibidas."],
        prompt_version="1.0",
    )

    at = AppTest.from_function(_render_results_with_state, kwargs={"job_result_payload": result.model_dump()})
    at.run(timeout=10)

    page_text = _page_text(at)
    assert "no supero la auditoria de vacantes" in page_text
    assert "keyword no aparece" in page_text
    assert "Familia de roles" not in page_text


def test_reprocess_jobs_failure_preserves_existing_market(monkeypatch):
    calls = {"count": 0}

    def fake_reprocess(*args, **kwargs):
        import streamlit as st

        calls["count"] += 1
        result = JobAnalysisResult(
            success=False,
            model_used="quality-model",
            error_category="timeout_error",
            user_message="La solicitud tardo mas de lo permitido. Intenta nuevamente.",
            retryable=True,
        )
        st.session_state[SessionKeys.JOB_ANALYSIS_RESULT] = result.model_dump()
        return result

    monkeypatch.setattr("components.result_views.run_job_analysis_from_session", fake_reprocess)
    previous = JobAnalysisResult(
        success=True,
        market_analysis=_market_analysis(),
        model_used="quality-model",
        audit_passed=True,
    )

    at = AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "job_result_payload": previous.model_dump(),
            "market_payload": _market_analysis().model_dump(),
            "validated_input_payload": _validated_input_payload(),
            "jobs_fingerprint": "old-jobs-fingerprint",
        },
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Reprocesar vacantes").click()
    at.run(timeout=10)

    assert calls["count"] == 1
    assert at.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] is not None
    assert at.session_state[SessionKeys.JOB_ANALYSIS_RESULT]["success"] is False
    assert "mercado objetivo" in at.session_state[SessionKeys.PROCESS_ERROR]


def test_process_runs_candidate_then_job_analysis_with_jobs_only(monkeypatch):
    calls = {"candidate_count": 0, "job_count": 0, "compatibility_count": 0, "jobs_payload": None, "language": None}

    def fake_candidate_pipeline(candidate_input, **kwargs):
        calls["candidate_count"] += 1
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=True,
                profile=_profile(),
                model_used="quality-model",
                evidence_audit_passed=True,
            ),
            fingerprint="candidate-fingerprint",
            reused=False,
        )

    def fake_job_pipeline(jobs, output_language, **kwargs):
        calls["job_count"] += 1
        calls["jobs_payload"] = [job.model_dump() for job in jobs]
        calls["language"] = output_language
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
        calls["compatibility_count"] += 1
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
    assert calls["candidate_count"] == 1
    assert calls["job_count"] == 1
    assert calls["compatibility_count"] == 1
    assert calls["language"] == OutputLanguage.ES
    jobs_payload = str(calls["jobs_payload"])
    assert "Responsabilidad exclusiva de vacante" in jobs_payload
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in jobs_payload
    assert "LinkedIn SECRETO" not in jobs_payload
    assert at.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] is not None
    assert at.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] is not None


def test_process_job_analysis_failure_explains_stage_after_input(monkeypatch):
    def fake_candidate_pipeline(candidate_input, **kwargs):
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=True,
                profile=_profile(),
                model_used="quality-model",
                evidence_audit_passed=True,
            ),
            fingerprint="candidate-fingerprint",
            reused=False,
        )

    def fake_job_pipeline(jobs, output_language, **kwargs):
        return JobAnalysisRun(
            result=JobAnalysisResult(
                success=False,
                model_used="quality-model",
                error_category="job_analysis_audit_failed",
                user_message="La respuesta fue recibida, pero no supero la auditoria de vacantes.",
                audit_findings=[
                    "warning: keywords[14]: La keyword parece aparecer en una vacante no incluida en job_indices.",
                    "error: keywords[0]: keyword no aparece en las vacantes recibidas.",
                ],
                retryable=False,
            ),
            fingerprint="jobs-fingerprint",
            reused=False,
        )

    def forbidden_linkedin_pipeline(*args, **kwargs):
        raise AssertionError("LinkedIn generation should not run when job analysis fails.")

    def forbidden_compatibility_pipeline(*args, **kwargs):
        raise AssertionError("Compatibility should not run when job analysis fails.")

    monkeypatch.setattr("components.candidate_extraction_flow.run_candidate_extraction_pipeline", fake_candidate_pipeline)
    monkeypatch.setattr("components.job_analysis_flow.run_job_analysis_pipeline", fake_job_pipeline)
    monkeypatch.setattr("components.compatibility_flow.run_compatibility_pipeline", forbidden_compatibility_pipeline)
    monkeypatch.setattr("components.linkedin_profile_flow.run_linkedin_profile_generation_pipeline", forbidden_linkedin_pipeline)
    at = AppTest.from_file("app.py").run(timeout=10)
    _fill_valid_form(at)
    next(button for button in at.button if button.label == "Procesar").click()
    at.run(timeout=10)

    process_error = at.session_state[SessionKeys.PROCESS_ERROR]
    assert "Las vacantes sí fueron recibidas" in process_error
    assert "Categoría técnica: job_analysis_audit_failed" in process_error
    assert "keyword no aparece" in process_error
    assert process_error.index("Errores principales") < process_error.index("Advertencias principales")
    assert at.session_state[SessionKeys.JOB_ANALYSIS_RESULT]["success"] is False
    assert at.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] is None


def test_clear_removes_job_analysis_state():
    result = JobAnalysisResult(
        success=True,
        market_analysis=_market_analysis(),
        model_used="quality-model",
        audit_passed=True,
    )
    at = AppTest.from_function(
        _render_results_with_clear,
        kwargs={"job_result_payload": result.model_dump(), "market_payload": _market_analysis().model_dump()},
    )
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Limpiar").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.JOB_ANALYSIS_RESULT] is None
    assert at.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] is None
    assert at.session_state[SessionKeys.JOB_ANALYSIS_AUDIT] is None


def _render_results_with_state(
    job_result_payload=None,
    market_payload=None,
    validated_input_payload=None,
    jobs_fingerprint=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_job_ui_test_seeded"):
        st.session_state["_job_ui_test_seeded"] = True
        if job_result_payload is not None:
            st.session_state[SessionKeys.JOB_ANALYSIS_RESULT] = job_result_payload
        if market_payload is not None:
            st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        if validated_input_payload is not None:
            st.session_state[SessionKeys.VALIDATED_INPUT] = validated_input_payload
        if jobs_fingerprint is not None:
            st.session_state[SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT] = jobs_fingerprint
    render_results()


def _render_results_with_clear(job_result_payload=None, market_payload=None):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, consume_clear_request, initialize_session_state, request_clear_session_state

    initialize_session_state()
    if not st.session_state.get("_job_ui_test_seeded"):
        st.session_state["_job_ui_test_seeded"] = True
        if job_result_payload is not None:
            st.session_state[SessionKeys.JOB_ANALYSIS_RESULT] = job_result_payload
        if market_payload is not None:
            st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
    st.button("Limpiar", on_click=request_clear_session_state)
    consume_clear_request()
    render_results()


def _fill_valid_form(at: AppTest) -> None:
    long_cv = (
        "CV_COMPLETO_NO_DEBE_MOSTRARSE Maria Ejemplo Senior Project Manager en Empresa Demo. "
        "Responsable de coordinar proyectos de transformacion digital y gestionar riesgos. "
        "Lidero implementaciones internas con equipos multidisciplinarios y reportes ejecutivos. "
        "Educacion Maestria en Administracion de Tecnologias. Idiomas Espanol nativo e Ingles intermedio. "
    )
    long_job = "Responsabilidad exclusiva de vacante para analizar mercado objetivo con Agile y riesgos. " * 3
    at.checkbox[0].check()
    at.text_area[0].set_value(long_cv)
    at.text_area[1].set_value("LinkedIn SECRETO que no debe llegar a job analysis.")
    at.text_input[1].set_value("Project Manager")
    at.text_area[2].set_value(long_job)
    at.text_input[4].set_value("Program Manager")
    at.text_area[3].set_value(long_job)


def _validated_input_payload() -> dict:
    cv_text = "CV_COMPLETO_NO_DEBE_MOSTRARSE Maria Ejemplo Project Manager. Gestion de proyectos. " * 4
    candidate_input = CandidateInput(
        cv_text=cv_text,
        cv_source=ContentSource.TEXT,
        cv_parse_summary=DocumentParseSummary(
            source=ContentSource.TEXT,
            character_count=len(cv_text),
            word_count=len(cv_text.split()),
        ),
        linkedin_text="LinkedIn SECRETO",
        linkedin_source=ContentSource.TEXT,
        output_language=OutputLanguage.ES,
        jobs=[
            JobInput(
                index=1,
                title="Project Manager",
                description="Responsabilidad exclusiva de vacante con Agile y riesgos. " * 3,
                source=ContentSource.TEXT,
            ),
            JobInput(
                index=2,
                title="Program Manager",
                description="Responsabilidad exclusiva de vacante con Agile y riesgos. " * 3,
                source=ContentSource.TEXT,
            ),
        ],
    )
    return candidate_input.model_dump()


def _profile() -> CandidateProfessionalProfile:
    reference = EvidenceReference(
        source_section="CV - Experiencia",
        source_excerpt="Responsable de coordinar proyectos de transformacion digital",
    )
    skill = CandidateSkill(
        name="Gestion de proyectos",
        normalized_name="gestion de proyectos",
        category=SkillCategory.BUSINESS,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.9,
        references=[reference],
    )
    responsibility = EvidenceItem(
        statement="Coordino proyectos de transformacion digital.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.88,
        references=[reference],
    )
    return CandidateProfessionalProfile(
        professional_identity="Project Manager",
        targetable_roles=["Project Manager"],
        summary="Project Manager con experiencia respaldada en transformacion digital.",
        seniority=SeniorityLevel.MANAGER,
        industries=["Tecnologia"],
        employment_history=[
            EmploymentEntry(
                employer="Empresa Demo",
                role_title="Senior Project Manager",
                start_date="2018",
                end_date="2025",
                responsibilities=[responsibility],
                technologies=[skill],
                industries=["Tecnologia"],
            )
        ],
        skills=[skill],
        leadership_capabilities=[responsibility],
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
        business_skills=["gestionar riesgos"],
        differentiators=["reportes ejecutivos"],
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


def _table_text(at: AppTest) -> str:
    return "\n".join(str(table.value) for table in at.table)
