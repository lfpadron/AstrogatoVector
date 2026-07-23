"""Streamlit session orchestration for candidate extraction."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import streamlit as st

from schemas.extraction_models import CandidateExtractionResult
from schemas.input_models import CandidateInput
from services.candidate_extraction_pipeline import (
    CandidateExtractionRun,
    run_candidate_extraction_pipeline,
)
from utils.session import SessionKeys, clear_compatibility_state, clear_linkedin_profile_generation_state

EXTRACTION_SUCCESS_MESSAGE = (
    "El perfil profesional fue extraído y validado correctamente.\n\n"
    "Revisa especialmente las inferencias, ambigüedades y conflictos antes de utilizar esta "
    "información en etapas posteriores."
)
REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de extracción falló. Se conserva el último perfil profesional válido de esta sesión."
)


def run_candidate_extraction_from_session(
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> CandidateExtractionResult:
    """Run candidate extraction from the current validated input in session state."""
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if not raw_input:
        result = CandidateExtractionResult(
            success=False,
            error_category="missing_validated_input",
            user_message="No existe una entrada validada para extraer el perfil profesional.",
            retryable=False,
        )
        _store_extraction_result(result, None, preserve_previous_on_failure=False)
        return result

    candidate_input = CandidateInput.model_validate(raw_input)
    existing_result = _current_extraction_result()
    existing_fingerprint = st.session_state.get(SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT)
    run = run_candidate_extraction_pipeline(
        candidate_input,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_extraction_result(run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def _store_extraction_result(
    result: CandidateExtractionResult,
    run: CandidateExtractionRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    st.session_state[SessionKeys.CANDIDATE_EXTRACTION_RESULT] = result.model_dump()
    st.session_state[SessionKeys.CANDIDATE_EVIDENCE_AUDIT] = result.evidence_audit_findings
    st.session_state[SessionKeys.CANDIDATE_EXTRACTION_LAST_RUN] = datetime.now().isoformat(timespec="seconds")

    if result.success and result.profile is not None:
        st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = result.profile.model_dump()
        st.session_state[SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT] = run.fingerprint if run else None
        if run is not None and not run.reused:
            clear_compatibility_state()
            clear_linkedin_profile_generation_state()
        return

    if preserve_previous_on_failure and st.session_state.get(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE):
        st.session_state[SessionKeys.PROCESS_ERROR] = REPROCESS_FAILURE_MESSAGE
        return

    st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = None
    st.session_state[SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT] = None


def _current_extraction_result() -> CandidateExtractionResult | None:
    raw_result = st.session_state.get(SessionKeys.CANDIDATE_EXTRACTION_RESULT)
    if not raw_result:
        return None
    try:
        return CandidateExtractionResult.model_validate(raw_result)
    except ValueError:
        return None
