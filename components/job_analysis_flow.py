"""Streamlit session orchestration for target jobs analysis."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import streamlit as st

from schemas.input_models import CandidateInput
from schemas.job_analysis_models import JobAnalysisResult
from services.job_analysis_pipeline import JobAnalysisRun, run_job_analysis_pipeline
from utils.session import SessionKeys, clear_compatibility_state, clear_linkedin_profile_generation_state

JOB_ANALYSIS_SUCCESS_MESSAGE = (
    "El mercado objetivo fue analizado y validado correctamente.\n\n"
    "Este análisis describe patrones y requisitos presentes en las vacantes seleccionadas. "
    "No implica que el candidato posea todas estas competencias."
)
JOB_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de análisis de vacantes falló. Se conserva el último mercado objetivo válido de esta sesión."
)


def run_job_analysis_from_session(
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> JobAnalysisResult:
    """Run target market analysis from the current validated input in session state."""
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if not raw_input:
        result = JobAnalysisResult(
            success=False,
            error_category="missing_validated_input",
            user_message="No existe una entrada validada para analizar las vacantes.",
            retryable=False,
        )
        _store_job_analysis_result(result, None, preserve_previous_on_failure=False)
        return result

    candidate_input = CandidateInput.model_validate(raw_input)
    existing_result = _current_job_analysis_result()
    existing_fingerprint = st.session_state.get(SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT)
    run = run_job_analysis_pipeline(
        candidate_input.jobs,
        candidate_input.output_language,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_job_analysis_result(run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def _store_job_analysis_result(
    result: JobAnalysisResult,
    run: JobAnalysisRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    st.session_state[SessionKeys.JOB_ANALYSIS_RESULT] = result.model_dump()
    st.session_state[SessionKeys.JOB_ANALYSIS_AUDIT] = result.audit_findings
    st.session_state[SessionKeys.JOBS_ANALYSIS_LAST_RUN] = datetime.now().isoformat(timespec="seconds")
    st.session_state[SessionKeys.JOBS_ANALYSIS_PROMPT_VERSION] = result.prompt_version

    if result.success and result.market_analysis is not None:
        st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = result.market_analysis.model_dump()
        st.session_state[SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT] = run.fingerprint if run else None
        if run is not None and not run.reused:
            clear_compatibility_state()
            clear_linkedin_profile_generation_state()
        return

    if preserve_previous_on_failure and st.session_state.get(SessionKeys.TARGET_MARKET_ANALYSIS):
        st.session_state[SessionKeys.PROCESS_ERROR] = JOB_REPROCESS_FAILURE_MESSAGE
        return

    st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = None
    st.session_state[SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT] = None


def _current_job_analysis_result() -> JobAnalysisResult | None:
    raw_result = st.session_state.get(SessionKeys.JOB_ANALYSIS_RESULT)
    if not raw_result:
        return None
    try:
        return JobAnalysisResult.model_validate(raw_result)
    except ValueError:
        return None
