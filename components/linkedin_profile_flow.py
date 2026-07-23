"""Streamlit session orchestration for LinkedIn profile generation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from schemas.profile_models import LinkedInProfileOutput
from services.linkedin_profile_generation_pipeline import (
    LinkedInProfileGenerationRun,
    run_linkedin_profile_generation_pipeline,
)
from utils.session import SessionKeys, clear_banner_render_state

LINKEDIN_PROFILE_SUCCESS_MESSAGE = (
    "El perfil de LinkedIn fue generado y validado correctamente.\n\n"
    "Revisa y adapta los textos antes de publicarlos. Astrogato Vector optimiza la presentación "
    "de la evidencia disponible, pero no sustituye la revisión profesional del usuario."
)
LINKEDIN_PROFILE_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de generación del perfil de LinkedIn falló. "
    "Se conserva el último perfil generado válido de esta sesión."
)
LINKEDIN_PROFILE_MISSING_STAGES_MESSAGE = (
    "Para generar el perfil de LinkedIn se necesita primero un perfil profesional válido "
    "y un análisis válido de las vacantes."
)


def run_linkedin_profile_generation_from_session(
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> LinkedInProfileGenerationResult:
    """Run LinkedIn profile generation from the current session state."""
    profile = _current_candidate_profile()
    market = _current_market_analysis()
    output_language = _current_output_language()
    if profile is None or market is None:
        result = LinkedInProfileGenerationResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=LINKEDIN_PROFILE_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        _store_generation_result(result, None, preserve_previous_on_failure=False)
        return result

    existing_result = _current_generation_result()
    existing_fingerprint = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT)
    run = run_linkedin_profile_generation_pipeline(
        profile,
        market,
        output_language,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_generation_result(run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def build_linkedin_profile_edit_state(output: LinkedInProfileOutput) -> dict[str, Any]:
    """Create editable state from an audited LinkedIn profile output."""
    return {
        "edited": False,
        "banner": {
            "primary_line": output.banner.primary_line,
            "specialty_line": output.banner.specialty_line,
            "supporting_line": output.banner.supporting_line or "",
            "visual_concept": output.banner.visual_concept,
            "recommended_template": output.banner.recommended_template,
        },
        "headline": output.headline.text,
        "about": output.about.text,
        "experience": [
            {
                "employer": item.employer,
                "source_role_title": item.source_role_title,
                "suggested_role_title": item.suggested_role_title,
                "rewritten_text": item.rewritten_text,
                "included_keywords": item.included_keywords,
            }
            for item in output.experience
        ],
        "selected_skills": [skill.name for skill in output.prioritized_skills],
        "selected_keywords": [keyword.keyword for keyword in output.ats_keywords],
    }


def _store_generation_result(
    result: LinkedInProfileGenerationResult,
    run: LinkedInProfileGenerationRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] = result.model_dump()
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_AUDIT] = result.audit_findings
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_LAST_RUN] = datetime.now().isoformat(timespec="seconds")
    st.session_state[SessionKeys.LINKEDIN_PROFILE_PROMPT_VERSION] = result.prompt_version

    if result.success and result.profile_output is not None:
        st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = result.profile_output.model_dump()
        st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT] = run.fingerprint if run else None
        st.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] = build_linkedin_profile_edit_state(result.profile_output)
        clear_banner_render_state()
        return

    if preserve_previous_on_failure and st.session_state.get(SessionKeys.LINKEDIN_PROFILE_OUTPUT):
        st.session_state[SessionKeys.PROCESS_ERROR] = LINKEDIN_PROFILE_REPROCESS_FAILURE_MESSAGE
        return

    st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] = None
    clear_banner_render_state()


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


def _current_generation_result() -> LinkedInProfileGenerationResult | None:
    raw = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT)
    if not raw:
        return None
    try:
        return LinkedInProfileGenerationResult.model_validate(raw)
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
