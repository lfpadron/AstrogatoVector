"""Centralized Streamlit session state management."""

from __future__ import annotations

from typing import Any

import streamlit as st

from utils.constants import DEFAULT_OUTPUT_LANGUAGE, MAX_JOB_POSTINGS, MIN_JOB_POSTINGS


class SessionKeys:
    """Session state keys used by the interface."""

    CV_TEXT = "cv_text"
    LINKEDIN_TEXT = "linkedin_text"
    LINKEDIN_URL = "linkedin_url"
    JOB_COUNT = "job_count"
    OUTPUT_LANGUAGE = "output_language"
    HAS_PROCESSED = "has_processed"
    PROCESS_MESSAGE = "process_message"
    PROCESS_ERROR = "process_error"
    VALIDATION_MESSAGES = "validation_messages"
    INPUT_SUMMARY = "input_summary"
    VALIDATED_INPUT = "validated_input"
    CV_PARSE_SUMMARY = "cv_parse_summary"
    CV_PARSE_RESULT = "cv_parse_result"
    CV_PREVIEW = "cv_preview"
    LINKEDIN_LINK_SUMMARY = "linkedin_link_summary"
    JOB_LINK_SUMMARIES = "job_link_summaries"
    LINK_ERROR = "link_error"
    FAILED_LINK_INDEX = "failed_link_index"
    LINK_PREVIEWS = "link_previews"
    RECOVERED_LINK_TEXTS = "recovered_link_texts"
    LINK_READING_COMPLETED = "link_reading_completed"
    OPENAI_DIAGNOSTIC_RESULT = "openai_diagnostic_result"
    OPENAI_DIAGNOSTIC_LAST_RUN = "openai_diagnostic_last_run"
    OPENAI_DIAGNOSTIC_RUNNING = "openai_diagnostic_running"
    CANDIDATE_EXTRACTION_RESULT = "candidate_extraction_result"
    CANDIDATE_PROFESSIONAL_PROFILE = "candidate_professional_profile"
    CANDIDATE_EVIDENCE_AUDIT = "candidate_evidence_audit"
    CANDIDATE_EXTRACTION_LAST_RUN = "candidate_extraction_last_run"
    CANDIDATE_EXTRACTION_INPUT_FINGERPRINT = "candidate_extraction_input_fingerprint"
    JOB_ANALYSIS_RESULT = "job_analysis_result"
    TARGET_MARKET_ANALYSIS = "target_market_analysis"
    JOB_ANALYSIS_AUDIT = "job_analysis_audit"
    JOBS_ANALYSIS_LAST_RUN = "jobs_analysis_last_run"
    JOBS_ANALYSIS_INPUT_FINGERPRINT = "jobs_analysis_input_fingerprint"
    JOBS_ANALYSIS_PROMPT_VERSION = "jobs_analysis_prompt_version"
    LINKEDIN_PROFILE_GENERATION_RESULT = "linkedin_profile_generation_result"
    LINKEDIN_PROFILE_OUTPUT = "linkedin_profile_output"
    LINKEDIN_PROFILE_GENERATION_AUDIT = "linkedin_profile_generation_audit"
    LINKEDIN_PROFILE_GENERATION_LAST_RUN = "linkedin_profile_generation_last_run"
    LINKEDIN_PROFILE_GENERATION_FINGERPRINT = "linkedin_profile_generation_fingerprint"
    LINKEDIN_PROFILE_PROMPT_VERSION = "linkedin_profile_prompt_version"
    LINKEDIN_PROFILE_EDIT_STATE = "linkedin_profile_edit_state"
    COMPATIBILITY_INPUT_FINGERPRINT = "compatibility_input_fingerprint"
    COMPATIBILITY_ANALYSIS_RESULT = "compatibility_analysis_result"
    COMPATIBILITY_SEMANTIC_EVALUATION = "compatibility_semantic_evaluation"
    COMPATIBILITY_REPORT = "compatibility_report"
    COMPATIBILITY_AUDIT = "compatibility_audit"
    COMPATIBILITY_LAST_RUN = "compatibility_last_run"
    COMPATIBILITY_METHODOLOGY_VERSION = "compatibility_methodology_version"
    FINAL_AUDIT_REPORT = "final_audit_report"
    FINAL_AUDIT_FINGERPRINT = "final_audit_fingerprint"
    FINAL_AUDIT_LOCAL_AUDIT = "final_audit_local_audit"
    FINAL_AUDIT_LAST_RUN = "final_audit_last_run"
    FINAL_AUDIT_PROMPT_VERSION = "final_audit_prompt_version"
    FINAL_AUDIT_METHODOLOGY_VERSION = "final_audit_methodology_version"
    FINAL_PACKAGE_BUILD_RESULT = "final_package_build_result"
    FINAL_PACKAGE_FINGERPRINT = "final_package_fingerprint"
    FINAL_PACKAGE_LAST_BUILD = "final_package_last_build"
    FINAL_PACKAGE_MARKDOWN_BYTES = "final_package_markdown_bytes"
    FINAL_PACKAGE_HTML_BYTES = "final_package_html_bytes"
    FINAL_PACKAGE_DOCX_BYTES = "final_package_docx_bytes"
    FINAL_PACKAGE_PDF_BYTES = "final_package_pdf_bytes"
    FINAL_PACKAGE_ZIP_BYTES = "final_package_zip_bytes"
    TARGETED_CV_GENERATION_RESULTS = "targeted_cv_generation_results"
    TARGETED_CVS = "targeted_cvs"
    TARGETED_CV_AUDITS = "targeted_cv_audits"
    TARGETED_CV_ATS_AUDITS = "targeted_cv_ats_audits"
    TARGETED_CV_INPUT_FINGERPRINTS = "targeted_cv_input_fingerprints"
    TARGETED_CV_EDIT_STATES = "targeted_cv_edit_states"
    TARGETED_CV_EDIT_VALIDATIONS = "targeted_cv_edit_validations"
    TARGETED_CV_EXPORT_FINGERPRINTS = "targeted_cv_export_fingerprints"
    TARGETED_CV_MARKDOWN_BYTES = "targeted_cv_markdown_bytes"
    TARGETED_CV_DOCX_BYTES = "targeted_cv_docx_bytes"
    TARGETED_CV_PDF_BYTES = "targeted_cv_pdf_bytes"
    TARGETED_CV_ZIP_BYTES = "targeted_cv_zip_bytes"
    TARGETED_CV_LAST_RUNS = "targeted_cv_last_runs"
    BANNER_RENDER_FINGERPRINT = "banner_render_fingerprint"
    BANNER_RENDER_RESULT = "banner_render_result"
    BANNER_IMAGE_BYTES = "banner_image_bytes"
    BANNER_LAST_RENDER = "banner_last_render"
    FUTURE_RESULTS = "future_results"
    CV_FILE_NAME = "cv_file_name"
    CV_FILE_SIZE = "cv_file_size"
    CONSENT_ACCEPTED = "consent_accepted"
    UPLOADER_VERSION = "uploader_version"
    CV_FILE_UPLOADER_RESET_INDEX = UPLOADER_VERSION
    CLEAR_REQUESTED = "clear_requested"


JOB_FIELDS = ("title", "company", "description", "url")


def get_job_field_key(index: int, field: str) -> str:
    """Return the centralized key for a job field."""
    if field not in JOB_FIELDS:
        raise ValueError(f"Campo de vacante no reconocido: {field}")
    return f"job_{index + 1}_{field}"


def get_cv_file_uploader_key() -> str:
    """Return the active file uploader key."""
    reset_index = st.session_state.get(SessionKeys.UPLOADER_VERSION, 0)
    return f"cv_file_uploader_{reset_index}"


def build_session_defaults() -> dict[str, Any]:
    """Return default values for all top-level session keys."""
    return {
        SessionKeys.CV_TEXT: "",
        SessionKeys.LINKEDIN_TEXT: "",
        SessionKeys.LINKEDIN_URL: "",
        SessionKeys.JOB_COUNT: MIN_JOB_POSTINGS,
        SessionKeys.OUTPUT_LANGUAGE: DEFAULT_OUTPUT_LANGUAGE,
        SessionKeys.HAS_PROCESSED: False,
        SessionKeys.PROCESS_MESSAGE: None,
        SessionKeys.PROCESS_ERROR: None,
        SessionKeys.VALIDATION_MESSAGES: [],
        SessionKeys.INPUT_SUMMARY: None,
        SessionKeys.VALIDATED_INPUT: None,
        SessionKeys.CV_PARSE_SUMMARY: None,
        SessionKeys.CV_PARSE_RESULT: None,
        SessionKeys.CV_PREVIEW: None,
        SessionKeys.LINKEDIN_LINK_SUMMARY: None,
        SessionKeys.JOB_LINK_SUMMARIES: [],
        SessionKeys.LINK_ERROR: None,
        SessionKeys.FAILED_LINK_INDEX: None,
        SessionKeys.LINK_PREVIEWS: {},
        SessionKeys.RECOVERED_LINK_TEXTS: {},
        SessionKeys.LINK_READING_COMPLETED: False,
        SessionKeys.OPENAI_DIAGNOSTIC_RESULT: None,
        SessionKeys.OPENAI_DIAGNOSTIC_LAST_RUN: None,
        SessionKeys.OPENAI_DIAGNOSTIC_RUNNING: False,
        SessionKeys.CANDIDATE_EXTRACTION_RESULT: None,
        SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE: None,
        SessionKeys.CANDIDATE_EVIDENCE_AUDIT: None,
        SessionKeys.CANDIDATE_EXTRACTION_LAST_RUN: None,
        SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT: None,
        SessionKeys.JOB_ANALYSIS_RESULT: None,
        SessionKeys.TARGET_MARKET_ANALYSIS: None,
        SessionKeys.JOB_ANALYSIS_AUDIT: None,
        SessionKeys.JOBS_ANALYSIS_LAST_RUN: None,
        SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT: None,
        SessionKeys.JOBS_ANALYSIS_PROMPT_VERSION: None,
        SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT: None,
        SessionKeys.LINKEDIN_PROFILE_OUTPUT: None,
        SessionKeys.LINKEDIN_PROFILE_GENERATION_AUDIT: None,
        SessionKeys.LINKEDIN_PROFILE_GENERATION_LAST_RUN: None,
        SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT: None,
        SessionKeys.LINKEDIN_PROFILE_PROMPT_VERSION: None,
        SessionKeys.LINKEDIN_PROFILE_EDIT_STATE: None,
        SessionKeys.COMPATIBILITY_INPUT_FINGERPRINT: None,
        SessionKeys.COMPATIBILITY_ANALYSIS_RESULT: None,
        SessionKeys.COMPATIBILITY_SEMANTIC_EVALUATION: None,
        SessionKeys.COMPATIBILITY_REPORT: None,
        SessionKeys.COMPATIBILITY_AUDIT: None,
        SessionKeys.COMPATIBILITY_LAST_RUN: None,
        SessionKeys.COMPATIBILITY_METHODOLOGY_VERSION: None,
        SessionKeys.FINAL_AUDIT_REPORT: None,
        SessionKeys.FINAL_AUDIT_FINGERPRINT: None,
        SessionKeys.FINAL_AUDIT_LOCAL_AUDIT: None,
        SessionKeys.FINAL_AUDIT_LAST_RUN: None,
        SessionKeys.FINAL_AUDIT_PROMPT_VERSION: None,
        SessionKeys.FINAL_AUDIT_METHODOLOGY_VERSION: None,
        SessionKeys.FINAL_PACKAGE_BUILD_RESULT: None,
        SessionKeys.FINAL_PACKAGE_FINGERPRINT: None,
        SessionKeys.FINAL_PACKAGE_LAST_BUILD: None,
        SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES: None,
        SessionKeys.FINAL_PACKAGE_HTML_BYTES: None,
        SessionKeys.FINAL_PACKAGE_DOCX_BYTES: None,
        SessionKeys.FINAL_PACKAGE_PDF_BYTES: None,
        SessionKeys.FINAL_PACKAGE_ZIP_BYTES: None,
        SessionKeys.TARGETED_CV_GENERATION_RESULTS: {},
        SessionKeys.TARGETED_CVS: {},
        SessionKeys.TARGETED_CV_AUDITS: {},
        SessionKeys.TARGETED_CV_ATS_AUDITS: {},
        SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS: {},
        SessionKeys.TARGETED_CV_EDIT_STATES: {},
        SessionKeys.TARGETED_CV_EDIT_VALIDATIONS: {},
        SessionKeys.TARGETED_CV_EXPORT_FINGERPRINTS: {},
        SessionKeys.TARGETED_CV_MARKDOWN_BYTES: {},
        SessionKeys.TARGETED_CV_DOCX_BYTES: {},
        SessionKeys.TARGETED_CV_PDF_BYTES: {},
        SessionKeys.TARGETED_CV_ZIP_BYTES: None,
        SessionKeys.TARGETED_CV_LAST_RUNS: {},
        SessionKeys.BANNER_RENDER_FINGERPRINT: None,
        SessionKeys.BANNER_RENDER_RESULT: None,
        SessionKeys.BANNER_IMAGE_BYTES: None,
        SessionKeys.BANNER_LAST_RENDER: None,
        SessionKeys.FUTURE_RESULTS: {},
        SessionKeys.CV_FILE_NAME: None,
        SessionKeys.CV_FILE_SIZE: None,
        SessionKeys.CONSENT_ACCEPTED: False,
        SessionKeys.UPLOADER_VERSION: 0,
        SessionKeys.CLEAR_REQUESTED: False,
    }


def initialize_session_state() -> None:
    """Initialize all known session keys."""
    for key, value in build_session_defaults().items():
        st.session_state.setdefault(key, value)

    for index in range(MAX_JOB_POSTINGS):
        for field in JOB_FIELDS:
            st.session_state.setdefault(get_job_field_key(index, field), "")


def add_job_posting() -> None:
    """Increase the visible job posting count up to the configured maximum."""
    current_count = int(st.session_state[SessionKeys.JOB_COUNT])
    st.session_state[SessionKeys.JOB_COUNT] = min(current_count + 1, MAX_JOB_POSTINGS)


def remove_job_posting() -> None:
    """Decrease the visible job posting count down to the configured minimum."""
    current_count = int(st.session_state[SessionKeys.JOB_COUNT])
    st.session_state[SessionKeys.JOB_COUNT] = max(current_count - 1, MIN_JOB_POSTINGS)


def clear_processing_state() -> None:
    """Clear validation messages, summaries and future result placeholders."""
    st.session_state[SessionKeys.HAS_PROCESSED] = False
    st.session_state[SessionKeys.PROCESS_MESSAGE] = None
    st.session_state[SessionKeys.PROCESS_ERROR] = None
    st.session_state[SessionKeys.VALIDATION_MESSAGES] = []
    st.session_state[SessionKeys.INPUT_SUMMARY] = None
    st.session_state[SessionKeys.VALIDATED_INPUT] = None
    st.session_state[SessionKeys.CV_PARSE_SUMMARY] = None
    st.session_state[SessionKeys.CV_PARSE_RESULT] = None
    st.session_state[SessionKeys.CV_PREVIEW] = None
    st.session_state[SessionKeys.LINKEDIN_LINK_SUMMARY] = None
    st.session_state[SessionKeys.JOB_LINK_SUMMARIES] = []
    st.session_state[SessionKeys.LINK_ERROR] = None
    st.session_state[SessionKeys.FAILED_LINK_INDEX] = None
    st.session_state[SessionKeys.LINK_PREVIEWS] = {}
    st.session_state[SessionKeys.RECOVERED_LINK_TEXTS] = {}
    st.session_state[SessionKeys.LINK_READING_COMPLETED] = False
    st.session_state[SessionKeys.FUTURE_RESULTS] = {}


def clear_openai_diagnostic_state() -> None:
    """Clear only the safe OpenAI diagnostic metadata stored in session."""
    st.session_state[SessionKeys.OPENAI_DIAGNOSTIC_RESULT] = None
    st.session_state[SessionKeys.OPENAI_DIAGNOSTIC_LAST_RUN] = None
    st.session_state[SessionKeys.OPENAI_DIAGNOSTIC_RUNNING] = False


def clear_candidate_extraction_state() -> None:
    """Clear candidate extraction metadata and structured profile."""
    st.session_state[SessionKeys.CANDIDATE_EXTRACTION_RESULT] = None
    st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = None
    st.session_state[SessionKeys.CANDIDATE_EVIDENCE_AUDIT] = None
    st.session_state[SessionKeys.CANDIDATE_EXTRACTION_LAST_RUN] = None
    st.session_state[SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT] = None
    clear_targeted_cv_state()
    clear_final_audit_state()


def clear_job_analysis_state() -> None:
    """Clear target jobs analysis metadata and structured market analysis."""
    st.session_state[SessionKeys.JOB_ANALYSIS_RESULT] = None
    st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = None
    st.session_state[SessionKeys.JOB_ANALYSIS_AUDIT] = None
    st.session_state[SessionKeys.JOBS_ANALYSIS_LAST_RUN] = None
    st.session_state[SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT] = None
    st.session_state[SessionKeys.JOBS_ANALYSIS_PROMPT_VERSION] = None
    clear_targeted_cv_state()
    clear_final_audit_state()


def clear_linkedin_profile_generation_state() -> None:
    """Clear generated LinkedIn profile metadata, output and editable state."""
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_AUDIT] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_LAST_RUN] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_PROMPT_VERSION] = None
    st.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] = None
    clear_banner_render_state()
    clear_final_audit_state()


def clear_compatibility_state() -> None:
    """Clear compatibility metadata, semantic evaluation and score report."""
    st.session_state[SessionKeys.COMPATIBILITY_INPUT_FINGERPRINT] = None
    st.session_state[SessionKeys.COMPATIBILITY_ANALYSIS_RESULT] = None
    st.session_state[SessionKeys.COMPATIBILITY_SEMANTIC_EVALUATION] = None
    st.session_state[SessionKeys.COMPATIBILITY_REPORT] = None
    st.session_state[SessionKeys.COMPATIBILITY_AUDIT] = None
    st.session_state[SessionKeys.COMPATIBILITY_LAST_RUN] = None
    st.session_state[SessionKeys.COMPATIBILITY_METHODOLOGY_VERSION] = None
    clear_targeted_cv_state()
    clear_final_audit_state()


def clear_final_audit_state() -> None:
    """Clear final LinkedIn and ATS audit metadata."""
    st.session_state[SessionKeys.FINAL_AUDIT_REPORT] = None
    st.session_state[SessionKeys.FINAL_AUDIT_FINGERPRINT] = None
    st.session_state[SessionKeys.FINAL_AUDIT_LOCAL_AUDIT] = None
    st.session_state[SessionKeys.FINAL_AUDIT_LAST_RUN] = None
    st.session_state[SessionKeys.FINAL_AUDIT_PROMPT_VERSION] = None
    st.session_state[SessionKeys.FINAL_AUDIT_METHODOLOGY_VERSION] = None
    clear_final_package_state()


def clear_final_package_state() -> None:
    """Clear generated final package bytes and metadata."""
    st.session_state[SessionKeys.FINAL_PACKAGE_BUILD_RESULT] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_FINGERPRINT] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_LAST_BUILD] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_HTML_BYTES] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_DOCX_BYTES] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_PDF_BYTES] = None
    st.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES] = None


def clear_targeted_cv_state() -> None:
    """Clear per-vacancy targeted CV outputs, edits and exports."""
    st.session_state[SessionKeys.TARGETED_CV_GENERATION_RESULTS] = {}
    st.session_state[SessionKeys.TARGETED_CVS] = {}
    st.session_state[SessionKeys.TARGETED_CV_AUDITS] = {}
    st.session_state[SessionKeys.TARGETED_CV_ATS_AUDITS] = {}
    st.session_state[SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS] = {}
    st.session_state[SessionKeys.TARGETED_CV_EDIT_STATES] = {}
    st.session_state[SessionKeys.TARGETED_CV_EDIT_VALIDATIONS] = {}
    st.session_state[SessionKeys.TARGETED_CV_EXPORT_FINGERPRINTS] = {}
    st.session_state[SessionKeys.TARGETED_CV_MARKDOWN_BYTES] = {}
    st.session_state[SessionKeys.TARGETED_CV_DOCX_BYTES] = {}
    st.session_state[SessionKeys.TARGETED_CV_PDF_BYTES] = {}
    st.session_state[SessionKeys.TARGETED_CV_ZIP_BYTES] = None
    st.session_state[SessionKeys.TARGETED_CV_LAST_RUNS] = {}


def clear_banner_render_state() -> None:
    """Clear transient in-memory banner render artifacts."""
    st.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] = None
    st.session_state[SessionKeys.BANNER_RENDER_RESULT] = None
    st.session_state[SessionKeys.BANNER_IMAGE_BYTES] = None
    st.session_state[SessionKeys.BANNER_LAST_RENDER] = None
    clear_final_package_state()


def sync_cv_file_metadata(file_name: str | None, file_size: int | None) -> None:
    """Store the current file reference without reading file contents."""
    st.session_state[SessionKeys.CV_FILE_NAME] = file_name
    st.session_state[SessionKeys.CV_FILE_SIZE] = file_size


def clear_session_state() -> None:
    """Reset form fields and transient messages to their initial values."""
    next_uploader_version = int(st.session_state.get(SessionKeys.UPLOADER_VERSION, 0)) + 1

    st.session_state[SessionKeys.CV_TEXT] = ""
    st.session_state[SessionKeys.LINKEDIN_TEXT] = ""
    st.session_state[SessionKeys.LINKEDIN_URL] = ""
    st.session_state[SessionKeys.JOB_COUNT] = MIN_JOB_POSTINGS
    st.session_state[SessionKeys.OUTPUT_LANGUAGE] = DEFAULT_OUTPUT_LANGUAGE
    st.session_state[SessionKeys.CONSENT_ACCEPTED] = False
    st.session_state[SessionKeys.CV_FILE_NAME] = None
    st.session_state[SessionKeys.CV_FILE_SIZE] = None
    st.session_state[SessionKeys.UPLOADER_VERSION] = next_uploader_version
    st.session_state[SessionKeys.CLEAR_REQUESTED] = False
    clear_processing_state()
    clear_openai_diagnostic_state()
    clear_candidate_extraction_state()
    clear_job_analysis_state()
    clear_compatibility_state()
    clear_linkedin_profile_generation_state()

    for index in range(MAX_JOB_POSTINGS):
        for field in JOB_FIELDS:
            st.session_state[get_job_field_key(index, field)] = ""

    for key in list(st.session_state.keys()):
        if str(key).startswith("cv_file_uploader_"):
            del st.session_state[key]


def request_clear_session_state() -> None:
    """Mark the form for clearing on the next render cycle."""
    st.session_state[SessionKeys.CLEAR_REQUESTED] = True


def consume_clear_request() -> None:
    """Clear the form before widgets are rendered when requested."""
    if st.session_state.get(SessionKeys.CLEAR_REQUESTED):
        clear_session_state()
        st.rerun()
