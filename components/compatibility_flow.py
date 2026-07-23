"""Streamlit session orchestration for compatibility analysis."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import streamlit as st

from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput
from schemas.market_models import TargetMarketAnalysis
from services.compatibility_pipeline import CompatibilityAnalysisRun, run_compatibility_pipeline
from utils.session import SessionKeys

COMPATIBILITY_SUCCESS_MESSAGE = (
    "La compatibilidad fue calculada y validada correctamente.\n\n"
    "Revisa las evidencias y brechas antes de decidir cómo adaptar tu perfil o preparar una postulación."
)
COMPATIBILITY_MISSING_STAGES_MESSAGE = (
    "Para calcular compatibilidad se necesita un perfil profesional válido y un análisis válido de las vacantes."
)
COMPATIBILITY_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de análisis de compatibilidad falló. "
    "Se conserva el último reporte de compatibilidad válido de esta sesión."
)


def run_compatibility_from_session(
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> CompatibilityAnalysisResult:
    """Run compatibility analysis from current session state."""
    profile = _current_candidate_profile()
    market = _current_market_analysis()
    output_language = _current_output_language()
    if profile is None or market is None:
        result = CompatibilityAnalysisResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=COMPATIBILITY_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        _store_compatibility_result(result, None, preserve_previous_on_failure=False)
        return result

    existing_result = _current_compatibility_result()
    existing_fingerprint = st.session_state.get(SessionKeys.COMPATIBILITY_INPUT_FINGERPRINT)
    run = run_compatibility_pipeline(
        profile,
        market,
        output_language,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_compatibility_result(run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def _store_compatibility_result(
    result: CompatibilityAnalysisResult,
    run: CompatibilityAnalysisRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    st.session_state[SessionKeys.COMPATIBILITY_ANALYSIS_RESULT] = result.model_dump()
    st.session_state[SessionKeys.COMPATIBILITY_AUDIT] = result.audit_findings
    st.session_state[SessionKeys.COMPATIBILITY_LAST_RUN] = datetime.now().isoformat(timespec="seconds")
    st.session_state[SessionKeys.COMPATIBILITY_METHODOLOGY_VERSION] = result.methodology_version

    if result.success and result.compatibility_report is not None and result.semantic_evaluation is not None:
        st.session_state[SessionKeys.COMPATIBILITY_REPORT] = result.compatibility_report.model_dump()
        st.session_state[SessionKeys.COMPATIBILITY_SEMANTIC_EVALUATION] = result.semantic_evaluation.model_dump()
        st.session_state[SessionKeys.COMPATIBILITY_INPUT_FINGERPRINT] = run.fingerprint if run else None
        return

    if preserve_previous_on_failure and st.session_state.get(SessionKeys.COMPATIBILITY_REPORT):
        st.session_state[SessionKeys.PROCESS_ERROR] = COMPATIBILITY_REPROCESS_FAILURE_MESSAGE
        return

    st.session_state[SessionKeys.COMPATIBILITY_REPORT] = None
    st.session_state[SessionKeys.COMPATIBILITY_SEMANTIC_EVALUATION] = None
    st.session_state[SessionKeys.COMPATIBILITY_INPUT_FINGERPRINT] = None


def _current_candidate_profile() -> CandidateProfessionalProfile | None:
    raw = st.session_state.get(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE)
    if not raw:
        return None
    try:
        return CandidateProfessionalProfile.model_validate(raw)
    except ValueError:
        return None


def _current_market_analysis() -> TargetMarketAnalysis | None:
    raw = st.session_state.get(SessionKeys.TARGET_MARKET_ANALYSIS)
    if not raw:
        return None
    try:
        return TargetMarketAnalysis.model_validate(raw)
    except ValueError:
        return None


def _current_compatibility_result() -> CompatibilityAnalysisResult | None:
    raw = st.session_state.get(SessionKeys.COMPATIBILITY_ANALYSIS_RESULT)
    if not raw:
        return None
    try:
        return CompatibilityAnalysisResult.model_validate(raw)
    except ValueError:
        return None


def _current_output_language() -> OutputLanguage | str:
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if raw_input:
        try:
            return CandidateInput.model_validate(raw_input).output_language
        except ValueError:
            pass
    return st.session_state.get(SessionKeys.OUTPUT_LANGUAGE, OutputLanguage.ES)
