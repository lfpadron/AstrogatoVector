"""Streamlit session orchestration for the final LinkedIn and ATS audit."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import streamlit as st

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_models import LinkedInProfileOutput
from services.final_audit_pipeline import FinalAuditRun, missing_final_audit_result, run_final_audit_pipeline
from utils.session import SessionKeys, clear_editorial_plan_state

FINAL_AUDIT_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de auditoría integral falló. "
    "Se conserva la última auditoría válida de esta sesión."
)


def run_final_audit_from_session(
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> AuditReport:
    """Run final audit from the current session state."""
    profile = _current_candidate_profile()
    market = _current_market_analysis()
    linkedin_output = _current_linkedin_profile_output()
    compatibility_report = _current_compatibility_report()
    if profile is None or market is None or linkedin_output is None or compatibility_report is None:
        result = missing_final_audit_result()
        _store_final_audit_result(result, None, preserve_previous_on_failure=False)
        return result

    existing_result = _current_final_audit_result()
    existing_fingerprint = st.session_state.get(SessionKeys.FINAL_AUDIT_FINGERPRINT)
    run = run_final_audit_pipeline(
        profile,
        market,
        linkedin_output,
        compatibility_report,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_final_audit_result(run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def _store_final_audit_result(
    result: AuditReport,
    run: FinalAuditRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    previous_fingerprint = st.session_state.get(SessionKeys.FINAL_AUDIT_FINGERPRINT)
    if (
        not result.success
        and preserve_previous_on_failure
        and st.session_state.get(SessionKeys.FINAL_AUDIT_REPORT)
    ):
        st.session_state[SessionKeys.PROCESS_ERROR] = FINAL_AUDIT_REPROCESS_FAILURE_MESSAGE
        st.session_state[SessionKeys.FINAL_AUDIT_LOCAL_AUDIT] = result.audit_findings
        st.session_state[SessionKeys.FINAL_AUDIT_LAST_RUN] = datetime.now().isoformat(timespec="seconds")
        return

    st.session_state[SessionKeys.FINAL_AUDIT_REPORT] = result.model_dump()
    st.session_state[SessionKeys.FINAL_AUDIT_LOCAL_AUDIT] = result.audit_findings
    st.session_state[SessionKeys.FINAL_AUDIT_LAST_RUN] = datetime.now().isoformat(timespec="seconds")
    st.session_state[SessionKeys.FINAL_AUDIT_PROMPT_VERSION] = result.prompt_version
    st.session_state[SessionKeys.FINAL_AUDIT_METHODOLOGY_VERSION] = result.methodology_version

    if result.success and result.linkedin_positioning is not None and result.ats_estimation is not None:
        new_fingerprint = run.fingerprint if run else None
        st.session_state[SessionKeys.FINAL_AUDIT_FINGERPRINT] = new_fingerprint
        if previous_fingerprint != new_fingerprint:
            clear_editorial_plan_state()
        return

    st.session_state[SessionKeys.FINAL_AUDIT_FINGERPRINT] = None
    clear_editorial_plan_state()


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


def _current_linkedin_profile_output() -> LinkedInProfileOutput | None:
    raw = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_OUTPUT)
    if not raw:
        return None
    try:
        return LinkedInProfileOutput.model_validate(raw)
    except ValueError:
        return None


def _current_compatibility_report() -> CompatibilityReport | None:
    raw = st.session_state.get(SessionKeys.COMPATIBILITY_REPORT)
    if not raw:
        return None
    try:
        return CompatibilityReport.model_validate(raw)
    except ValueError:
        return None


def _current_final_audit_result() -> AuditReport | None:
    raw = st.session_state.get(SessionKeys.FINAL_AUDIT_REPORT)
    if not raw:
        return None
    try:
        return AuditReport.model_validate(raw)
    except ValueError:
        return None
