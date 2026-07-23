from utils.constants import DEFAULT_OUTPUT_LANGUAGE, MIN_JOB_POSTINGS
from utils.session import SessionKeys, build_session_defaults


def test_session_defaults_cover_initial_state():
    defaults = build_session_defaults()

    assert defaults[SessionKeys.JOB_COUNT] == MIN_JOB_POSTINGS
    assert defaults[SessionKeys.OUTPUT_LANGUAGE] == DEFAULT_OUTPUT_LANGUAGE == "es"
    assert defaults[SessionKeys.CONSENT_ACCEPTED] is False
    assert defaults[SessionKeys.FUTURE_RESULTS] == {}
    assert defaults[SessionKeys.UPLOADER_VERSION] == 0
    assert defaults[SessionKeys.VALIDATED_INPUT] is None
    assert defaults[SessionKeys.VALIDATION_MESSAGES] == []
    assert defaults[SessionKeys.CV_PARSE_SUMMARY] is None
    assert defaults[SessionKeys.CV_PARSE_RESULT] is None
    assert defaults[SessionKeys.CV_PREVIEW] is None
    assert defaults[SessionKeys.LINKEDIN_LINK_SUMMARY] is None
    assert defaults[SessionKeys.JOB_LINK_SUMMARIES] == []
    assert defaults[SessionKeys.LINK_ERROR] is None
    assert defaults[SessionKeys.FAILED_LINK_INDEX] is None
    assert defaults[SessionKeys.LINK_PREVIEWS] == {}
    assert defaults[SessionKeys.RECOVERED_LINK_TEXTS] == {}
    assert defaults[SessionKeys.LINK_READING_COMPLETED] is False
    assert defaults[SessionKeys.OPENAI_DIAGNOSTIC_RESULT] is None
    assert defaults[SessionKeys.OPENAI_DIAGNOSTIC_LAST_RUN] is None
    assert defaults[SessionKeys.OPENAI_DIAGNOSTIC_RUNNING] is False
    assert defaults[SessionKeys.CANDIDATE_EXTRACTION_RESULT] is None
    assert defaults[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] is None
    assert defaults[SessionKeys.CANDIDATE_EVIDENCE_AUDIT] is None
    assert defaults[SessionKeys.CANDIDATE_EXTRACTION_LAST_RUN] is None
    assert defaults[SessionKeys.CANDIDATE_EXTRACTION_INPUT_FINGERPRINT] is None
    assert defaults[SessionKeys.JOB_ANALYSIS_RESULT] is None
    assert defaults[SessionKeys.TARGET_MARKET_ANALYSIS] is None
    assert defaults[SessionKeys.JOB_ANALYSIS_AUDIT] is None
    assert defaults[SessionKeys.JOBS_ANALYSIS_LAST_RUN] is None
    assert defaults[SessionKeys.JOBS_ANALYSIS_INPUT_FINGERPRINT] is None
    assert defaults[SessionKeys.JOBS_ANALYSIS_PROMPT_VERSION] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_OUTPUT] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_GENERATION_AUDIT] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_GENERATION_LAST_RUN] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_PROMPT_VERSION] is None
    assert defaults[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] is None
    assert defaults[SessionKeys.COMPATIBILITY_INPUT_FINGERPRINT] is None
    assert defaults[SessionKeys.COMPATIBILITY_ANALYSIS_RESULT] is None
    assert defaults[SessionKeys.COMPATIBILITY_SEMANTIC_EVALUATION] is None
    assert defaults[SessionKeys.COMPATIBILITY_REPORT] is None
    assert defaults[SessionKeys.COMPATIBILITY_AUDIT] is None
    assert defaults[SessionKeys.COMPATIBILITY_LAST_RUN] is None
    assert defaults[SessionKeys.COMPATIBILITY_METHODOLOGY_VERSION] is None
    assert defaults[SessionKeys.FINAL_AUDIT_REPORT] is None
    assert defaults[SessionKeys.FINAL_AUDIT_FINGERPRINT] is None
    assert defaults[SessionKeys.FINAL_AUDIT_LOCAL_AUDIT] is None
    assert defaults[SessionKeys.FINAL_AUDIT_LAST_RUN] is None
    assert defaults[SessionKeys.FINAL_AUDIT_PROMPT_VERSION] is None
    assert defaults[SessionKeys.FINAL_AUDIT_METHODOLOGY_VERSION] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_BUILD_RESULT] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_FINGERPRINT] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_LAST_BUILD] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_HTML_BYTES] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_DOCX_BYTES] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_PDF_BYTES] is None
    assert defaults[SessionKeys.FINAL_PACKAGE_ZIP_BYTES] is None
    assert defaults[SessionKeys.BANNER_RENDER_FINGERPRINT] is None
    assert defaults[SessionKeys.BANNER_RENDER_RESULT] is None
    assert defaults[SessionKeys.BANNER_IMAGE_BYTES] is None
    assert defaults[SessionKeys.BANNER_LAST_RENDER] is None
