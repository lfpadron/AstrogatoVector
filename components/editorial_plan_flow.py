"""Streamlit session orchestration for the LinkedIn professional editorial plan."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from exporters.editorial_plan_docx_exporter import EditorialPlanDocxExporter
from exporters.editorial_plan_html_exporter import EditorialPlanHTMLExporter
from exporters.editorial_plan_markdown_exporter import EditorialPlanMarkdownExporter
from exporters.editorial_plan_pdf_exporter import EditorialPlanPDFExporter
from exporters.editorial_plan_zip_exporter import EditorialPlanZipExporter
from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.editorial_plan_models import (
    EDITORIAL_PLAN_EXPORT_VERSION,
    EditorialPlanAuditResult,
    EditorialPlanEditValidationResult,
    EditorialPlanGenerationResult,
    ProfessionalBrandPlan,
)
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput
from schemas.market_models import TargetMarketAnalysis
from services.editorial_plan_audit_service import audit_editorial_plan
from services.editorial_plan_edit_validation_service import (
    apply_editorial_plan_edit_state,
    build_editorial_plan_edit_state,
    validate_editorial_plan_edits,
)
from services.editorial_plan_pipeline import (
    EDITORIAL_PLAN_MISSING_STAGES_MESSAGE,
    EditorialPlanGenerationRun,
    run_editorial_plan_generation_pipeline,
)
from services.export_audit_service import ExportAuditService
from utils.constants import DEFAULT_OUTPUT_LANGUAGE
from utils.session import SessionKeys

EDITORIAL_PLAN_SUCCESS_MESSAGE = "El plan editorial profesional fue generado y validado correctamente."
EDITORIAL_PLAN_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de generación del plan editorial falló. Se conserva el último plan válido de esta sesión."
)
EDITORIAL_PLAN_EXPORT_FAILURE_MESSAGE = (
    "El plan fue validado, pero uno o más archivos no superaron la auditoría local de exportación."
)
EDITORIAL_PLAN_EXPORT_SUCCESS_MESSAGE = "Los archivos del plan editorial quedaron listos para descargar."


def run_editorial_plan_from_session(
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = True,
    status_callback: Callable[[str], None] | None = None,
) -> EditorialPlanGenerationResult:
    """Run editorial plan generation from current session state."""
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    audit_report = _current_audit_report()
    output_language = _current_output_language()
    if profile is None or market is None or compatibility is None or audit_report is None or not audit_report.success:
        result = EditorialPlanGenerationResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=EDITORIAL_PLAN_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        _store_generation_result(result, None, preserve_previous_on_failure=False)
        return result

    existing_result = _current_generation_result()
    existing_fingerprint = st.session_state.get(SessionKeys.EDITORIAL_PLAN_INPUT_FINGERPRINT)
    run = run_editorial_plan_generation_pipeline(
        profile,
        market,
        compatibility,
        audit_report,
        output_language,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_generation_result(run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def build_editorial_plan_exports_from_session() -> dict[str, Any]:
    """Validate edits, export editorial plan bytes and store them in session."""
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    audit_report = _current_audit_report()
    plan = _current_plan()
    if profile is None or market is None or compatibility is None or audit_report is None or not audit_report.success:
        return {"success": False, "errors": [EDITORIAL_PLAN_MISSING_STAGES_MESSAGE]}
    if plan is None:
        return {"success": False, "errors": ["Primero genera un plan editorial profesional válido."]}

    edit_state = st.session_state.get(SessionKeys.EDITORIAL_PLAN_EDIT_STATE)
    edited_plan = apply_editorial_plan_edit_state(plan, edit_state)
    validation = validate_editorial_plan_edits(plan, profile, market, compatibility, audit_report, edit_state)
    st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_VALIDATION] = validation.model_dump()
    if not validation.passed:
        _clear_editorial_plan_bytes()
        return {"success": False, "errors": ["Los cambios del plan editorial no pasaron validación local."]}

    local_audit = audit_editorial_plan(edited_plan, profile, market, compatibility, audit_report)
    st.session_state[SessionKeys.EDITORIAL_PLAN_AUDIT] = local_audit.model_dump()
    if not local_audit.passed:
        _clear_editorial_plan_bytes()
        return {"success": False, "errors": ["El plan editorial editado no pasó auditoría local."]}

    export_fingerprint = _export_fingerprint(edited_plan)
    if (
        st.session_state.get(SessionKeys.EDITORIAL_PLAN_EXPORT_FINGERPRINT) == export_fingerprint
        and _editorial_plan_bytes_available()
    ):
        return {"success": True, "errors": []}

    markdown = EditorialPlanMarkdownExporter().export(edited_plan)
    html = EditorialPlanHTMLExporter().export(edited_plan)
    docx = EditorialPlanDocxExporter().export(edited_plan)
    pdf = EditorialPlanPDFExporter().export(edited_plan)
    zip_bytes = EditorialPlanZipExporter().export(edited_plan, edit_validation=validation)
    export_audit = ExportAuditService().audit_editorial_plan_all(
        {"markdown": markdown, "html": html, "docx": docx, "pdf": pdf, "zip": zip_bytes}
    )
    if not export_audit.passed:
        _clear_editorial_plan_bytes()
        return {"success": False, "errors": export_audit.findings}

    st.session_state[SessionKeys.EDITORIAL_PLAN_MARKDOWN_BYTES] = markdown
    st.session_state[SessionKeys.EDITORIAL_PLAN_HTML_BYTES] = html
    st.session_state[SessionKeys.EDITORIAL_PLAN_DOCX_BYTES] = docx
    st.session_state[SessionKeys.EDITORIAL_PLAN_PDF_BYTES] = pdf
    st.session_state[SessionKeys.EDITORIAL_PLAN_ZIP_BYTES] = zip_bytes
    st.session_state[SessionKeys.EDITORIAL_PLAN_EXPORT_FINGERPRINT] = export_fingerprint
    return {"success": True, "errors": []}


def current_editorial_plan_for_export() -> ProfessionalBrandPlan | None:
    """Return the edited editorial plan if one is available."""
    plan = _current_plan()
    if plan is None:
        return None
    return apply_editorial_plan_edit_state(plan, st.session_state.get(SessionKeys.EDITORIAL_PLAN_EDIT_STATE))


def _store_generation_result(
    result: EditorialPlanGenerationResult,
    run: EditorialPlanGenerationRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    st.session_state[SessionKeys.EDITORIAL_PLAN_GENERATION_RESULT] = result.model_dump()
    st.session_state[SessionKeys.EDITORIAL_PLAN_LAST_RUN] = datetime.now().isoformat(timespec="seconds")
    if result.success and result.professional_brand_plan is not None:
        st.session_state[SessionKeys.PROFESSIONAL_BRAND_PLAN] = result.professional_brand_plan.model_dump()
        if run and run.fingerprint:
            st.session_state[SessionKeys.EDITORIAL_PLAN_INPUT_FINGERPRINT] = run.fingerprint
        if run and run.audit:
            st.session_state[SessionKeys.EDITORIAL_PLAN_AUDIT] = run.audit.model_dump()
        edit_state = build_editorial_plan_edit_state(result.professional_brand_plan)
        edit_state["_source_fingerprint"] = run.fingerprint if run else None
        st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_STATE] = edit_state
        st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_VALIDATION] = None
        _clear_editorial_plan_bytes()
        return

    if preserve_previous_on_failure and st.session_state.get(SessionKeys.PROFESSIONAL_BRAND_PLAN):
        st.session_state[SessionKeys.PROCESS_ERROR] = EDITORIAL_PLAN_REPROCESS_FAILURE_MESSAGE
        return

    st.session_state[SessionKeys.PROFESSIONAL_BRAND_PLAN] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_AUDIT] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_INPUT_FINGERPRINT] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_STATE] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_VALIDATION] = None
    _clear_editorial_plan_bytes()


def _current_profile() -> CandidateProfessionalProfile | None:
    return _model_from_session(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE, CandidateProfessionalProfile)


def _current_market() -> TargetMarketAnalysis | None:
    return _model_from_session(SessionKeys.TARGET_MARKET_ANALYSIS, TargetMarketAnalysis)


def _current_compatibility() -> CompatibilityReport | None:
    return _model_from_session(SessionKeys.COMPATIBILITY_REPORT, CompatibilityReport)


def _current_audit_report() -> AuditReport | None:
    return _model_from_session(SessionKeys.FINAL_AUDIT_REPORT, AuditReport)


def _current_generation_result() -> EditorialPlanGenerationResult | None:
    return _model_from_session(SessionKeys.EDITORIAL_PLAN_GENERATION_RESULT, EditorialPlanGenerationResult)


def _current_plan() -> ProfessionalBrandPlan | None:
    return _model_from_session(SessionKeys.PROFESSIONAL_BRAND_PLAN, ProfessionalBrandPlan)


def _model_from_session(key: str, model_class):
    raw = st.session_state.get(key)
    if not raw:
        return None
    try:
        return model_class.model_validate(raw)
    except ValueError:
        return None


def _current_output_language() -> OutputLanguage | str:
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if raw_input:
        try:
            return CandidateInput.model_validate(raw_input).output_language
        except ValueError:
            pass
    return st.session_state.get(SessionKeys.OUTPUT_LANGUAGE, DEFAULT_OUTPUT_LANGUAGE)


def _editorial_plan_bytes_available() -> bool:
    return all(
        st.session_state.get(key)
        for key in (
            SessionKeys.EDITORIAL_PLAN_MARKDOWN_BYTES,
            SessionKeys.EDITORIAL_PLAN_HTML_BYTES,
            SessionKeys.EDITORIAL_PLAN_DOCX_BYTES,
            SessionKeys.EDITORIAL_PLAN_PDF_BYTES,
            SessionKeys.EDITORIAL_PLAN_ZIP_BYTES,
        )
    )


def _clear_editorial_plan_bytes() -> None:
    st.session_state[SessionKeys.EDITORIAL_PLAN_MARKDOWN_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_HTML_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_DOCX_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_PDF_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_ZIP_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_EXPORT_FINGERPRINT] = None


def _export_fingerprint(plan: ProfessionalBrandPlan) -> str:
    payload = {
        "export_version": EDITORIAL_PLAN_EXPORT_VERSION,
        "professional_brand_plan": plan.model_dump(mode="json", exclude={"generated_at"}),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
