"""Streamlit session orchestration for targeted CVs."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from exporters.targeted_cv_docx_exporter import TargetedCVDocxExporter
from exporters.targeted_cv_markdown_exporter import TargetedCVMarkdownExporter
from exporters.targeted_cv_pdf_exporter import TargetedCVPDFExporter
from exporters.targeted_cv_zip_exporter import TargetedCVZipExporter
from schemas.compatibility_models import CompatibilityReport, JobCompatibility
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput
from schemas.market_models import JobAnalysis, TargetMarketAnalysis
from schemas.targeted_cv_models import (
    TARGETED_CV_EXPORT_VERSION,
    TargetedCV,
    TargetedCVATSAudit,
    TargetedCVAuditResult,
    TargetedCVEditableValidationResult,
    TargetedCVGenerationResult,
)
from services.export_audit_service import ExportAuditService
from services.targeted_cv_audit_service import audit_targeted_cv
from services.targeted_cv_ats_audit_service import audit_targeted_cv_ats
from services.targeted_cv_edit_validation_service import (
    apply_targeted_cv_edit_state,
    build_targeted_cv_edit_state,
    validate_targeted_cv_edits,
)
from services.targeted_cv_pipeline import TargetedCVGenerationRun, run_targeted_cv_generation_pipeline
from utils.constants import DEFAULT_OUTPUT_LANGUAGE
from utils.session import SessionKeys

TARGETED_CV_SUCCESS_MESSAGE = "El CV específico por vacante fue generado y validado correctamente."
TARGETED_CV_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de generación del CV por vacante falló. Se conserva el último CV válido de esta sesión."
)
TARGETED_CV_MISSING_STAGES_MESSAGE = (
    "Para generar CVs por vacante se necesita primero un perfil profesional válido, "
    "un análisis válido de vacantes y compatibilidad válida."
)
TARGETED_CV_EXPORT_FAILURE_MESSAGE = (
    "El CV fue validado, pero uno o más archivos generados no superaron la auditoría local de exportación."
)
TARGETED_CV_EXPORT_SUCCESS_MESSAGE = "Los archivos del CV por vacante quedaron listos para descargar."


def run_targeted_cv_generation_from_session(
    job_index: int,
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = True,
    status_callback: Callable[[str], None] | None = None,
) -> TargetedCVGenerationResult:
    """Run targeted CV generation for one job from session state."""
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    output_language = _current_output_language()
    job_analysis = _job_analysis_by_index(market, job_index)
    job_compatibility = _job_compatibility_by_index(compatibility, job_index)
    if profile is None or market is None or compatibility is None or job_analysis is None or job_compatibility is None:
        result = TargetedCVGenerationResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=TARGETED_CV_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        _store_generation_result(job_index, result, None, preserve_previous_on_failure=False)
        return result

    existing_result = _current_generation_result(job_index)
    existing_fingerprint = _dict_get(SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS, job_index)
    run = run_targeted_cv_generation_pipeline(
        profile,
        job_analysis,
        job_compatibility,
        output_language,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_generation_result(job_index, run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def run_all_targeted_cv_generation_from_session(
    *,
    force: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> list[TargetedCVGenerationResult]:
    """Generate targeted CVs sequentially for all analyzed jobs."""
    market = _current_market()
    if market is None:
        result = TargetedCVGenerationResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=TARGETED_CV_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        return [result]
    results = []
    for job in sorted(market.job_analyses, key=lambda item: item.job_index):
        if status_callback:
            status_callback(f"Generando CV para vacante {job.job_index} de {len(market.job_analyses)}...")
        results.append(
            run_targeted_cv_generation_from_session(
                job.job_index,
                force=force,
                preserve_previous_on_failure=True,
                status_callback=status_callback,
            )
        )
    return results


def build_targeted_cv_exports_from_session(job_index: int | None = None) -> dict[str, Any]:
    """Validate edits, export targeted CV bytes and store them in session."""
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    if profile is None or market is None or compatibility is None:
        return {"success": False, "errors": [TARGETED_CV_MISSING_STAGES_MESSAGE], "exported_indices": []}

    indices = [job_index] if job_index is not None else sorted(_current_targeted_cvs().keys())
    exported_indices: list[int] = []
    errors: list[str] = []
    audits: dict[int, TargetedCVAuditResult] = {}
    ats_audits: dict[int, TargetedCVATSAudit] = {}
    validations: dict[int, TargetedCVEditableValidationResult] = {}

    for index in indices:
        cv = _current_targeted_cv(index)
        job_analysis = _job_analysis_by_index(market, index)
        job_compatibility = _job_compatibility_by_index(compatibility, index)
        if cv is None or job_analysis is None or job_compatibility is None:
            errors.append(f"Vacante {index}: no existe un CV generado y válido.")
            continue
        edited_cv = apply_targeted_cv_edit_state(cv, _dict_get(SessionKeys.TARGETED_CV_EDIT_STATES, index))
        validation = validate_targeted_cv_edits(
            cv,
            profile,
            job_analysis,
            job_compatibility,
            _dict_get(SessionKeys.TARGETED_CV_EDIT_STATES, index),
        )
        validations[index] = validation
        _dict_set(SessionKeys.TARGETED_CV_EDIT_VALIDATIONS, index, validation.model_dump())
        if not validation.passed:
            errors.append(f"Vacante {index}: los cambios del CV no pasaron validación local.")
            _clear_targeted_cv_bytes(index)
            continue

        export_fingerprint = _export_fingerprint(edited_cv)
        if (
            _dict_get(SessionKeys.TARGETED_CV_EXPORT_FINGERPRINTS, index) == export_fingerprint
            and _targeted_cv_bytes_available(index)
        ):
            exported_indices.append(index)
            audits[index] = audit_targeted_cv(edited_cv, profile, job_analysis, job_compatibility)
            ats_audits[index] = audit_targeted_cv_ats(edited_cv, profile, job_analysis, job_compatibility)
            continue

        markdown = TargetedCVMarkdownExporter().export(edited_cv)
        docx = TargetedCVDocxExporter().export(edited_cv)
        pdf = TargetedCVPDFExporter().export(edited_cv)
        audit_service = ExportAuditService()
        export_audit = audit_service.audit_targeted_cv_all({"markdown": markdown, "docx": docx, "pdf": pdf, "zip": b""})
        non_zip_findings = [finding for finding in export_audit.findings if not finding.startswith("targeted_cv_zip")]
        if non_zip_findings:
            errors.extend(non_zip_findings)
            _clear_targeted_cv_bytes(index)
            continue
        _dict_set(SessionKeys.TARGETED_CV_MARKDOWN_BYTES, index, markdown)
        _dict_set(SessionKeys.TARGETED_CV_DOCX_BYTES, index, docx)
        _dict_set(SessionKeys.TARGETED_CV_PDF_BYTES, index, pdf)
        _dict_set(SessionKeys.TARGETED_CV_EXPORT_FINGERPRINTS, index, export_fingerprint)
        audits[index] = audit_targeted_cv(edited_cv, profile, job_analysis, job_compatibility)
        ats_audits[index] = audit_targeted_cv_ats(edited_cv, profile, job_analysis, job_compatibility)
        exported_indices.append(index)

    if exported_indices:
        all_cvs = _edited_cvs_for_zip(profile, market, compatibility)
        zip_audits = {index: audit for index, audit in audits.items()}
        zip_ats = {index: audit for index, audit in ats_audits.items()}
        for cv in all_cvs:
            index = cv.target_job_index
            job_analysis = _job_analysis_by_index(market, index)
            job_compatibility = _job_compatibility_by_index(compatibility, index)
            if job_analysis and job_compatibility and index not in zip_audits:
                zip_audits[index] = audit_targeted_cv(cv, profile, job_analysis, job_compatibility)
                zip_ats[index] = audit_targeted_cv_ats(cv, profile, job_analysis, job_compatibility)
        zip_bytes = TargetedCVZipExporter().export(all_cvs, audits=zip_audits, ats_audits=zip_ats, edit_validations=validations)
        zip_audit = ExportAuditService().audit_targeted_cv_zip(zip_bytes)
        if zip_audit.passed:
            st.session_state[SessionKeys.TARGETED_CV_ZIP_BYTES] = zip_bytes
        else:
            st.session_state[SessionKeys.TARGETED_CV_ZIP_BYTES] = None
            errors.extend(zip_audit.findings)

    return {"success": bool(exported_indices) and not errors, "errors": errors, "exported_indices": exported_indices}


def current_targeted_cv_for_export(job_index: int) -> TargetedCV | None:
    """Return the edited, validated CV for one job if available."""
    cv = _current_targeted_cv(job_index)
    if cv is None:
        return None
    return apply_targeted_cv_edit_state(cv, _dict_get(SessionKeys.TARGETED_CV_EDIT_STATES, job_index))


def _store_generation_result(
    job_index: int,
    result: TargetedCVGenerationResult,
    run: TargetedCVGenerationRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    _dict_set(SessionKeys.TARGETED_CV_GENERATION_RESULTS, job_index, result.model_dump())
    _dict_set(SessionKeys.TARGETED_CV_LAST_RUNS, job_index, datetime.now().isoformat(timespec="seconds"))
    if result.success and result.targeted_cv is not None:
        _dict_set(SessionKeys.TARGETED_CVS, job_index, result.targeted_cv.model_dump())
        if run and run.fingerprint:
            _dict_set(SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS, job_index, run.fingerprint)
        audit = _current_local_audit(job_index, result.targeted_cv)
        if audit:
            _dict_set(SessionKeys.TARGETED_CV_AUDITS, job_index, audit.model_dump())
        if run and run.ats_audit:
            _dict_set(SessionKeys.TARGETED_CV_ATS_AUDITS, job_index, run.ats_audit.model_dump())
        edit_state = build_targeted_cv_edit_state(result.targeted_cv)
        edit_state["_source_fingerprint"] = run.fingerprint if run else None
        _dict_set(SessionKeys.TARGETED_CV_EDIT_STATES, job_index, edit_state)
        _dict_set(SessionKeys.TARGETED_CV_EDIT_VALIDATIONS, job_index, None)
        _clear_targeted_cv_bytes(job_index)
        _clear_application_communication_for_job(job_index)
        st.session_state[SessionKeys.TARGETED_CV_ZIP_BYTES] = None
        return

    if preserve_previous_on_failure and _dict_get(SessionKeys.TARGETED_CVS, job_index):
        st.session_state[SessionKeys.PROCESS_ERROR] = TARGETED_CV_REPROCESS_FAILURE_MESSAGE
        return

    _dict_set(SessionKeys.TARGETED_CVS, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_AUDITS, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_ATS_AUDITS, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_EDIT_STATES, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_EDIT_VALIDATIONS, job_index, None)
    _clear_targeted_cv_bytes(job_index)
    _clear_application_communication_for_job(job_index)


def _edited_cvs_for_zip(
    profile: CandidateProfessionalProfile,
    market: TargetMarketAnalysis,
    compatibility: CompatibilityReport,
) -> list[TargetedCV]:
    cvs: list[TargetedCV] = []
    for index in sorted(_current_targeted_cvs()):
        cv = _current_targeted_cv(index)
        job_analysis = _job_analysis_by_index(market, index)
        job_compatibility = _job_compatibility_by_index(compatibility, index)
        if cv is None or job_analysis is None or job_compatibility is None:
            continue
        edited_cv = apply_targeted_cv_edit_state(cv, _dict_get(SessionKeys.TARGETED_CV_EDIT_STATES, index))
        validation = validate_targeted_cv_edits(cv, profile, job_analysis, job_compatibility, _dict_get(SessionKeys.TARGETED_CV_EDIT_STATES, index))
        if validation.passed:
            cvs.append(edited_cv)
    return cvs


def _current_local_audit(job_index: int, cv: TargetedCV) -> TargetedCVAuditResult | None:
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    job_analysis = _job_analysis_by_index(market, job_index)
    job_compatibility = _job_compatibility_by_index(compatibility, job_index)
    if profile is None or job_analysis is None or job_compatibility is None:
        return None
    return audit_targeted_cv(cv, profile, job_analysis, job_compatibility)


def _current_profile() -> CandidateProfessionalProfile | None:
    return _model_from_session(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE, CandidateProfessionalProfile)


def _current_market() -> TargetMarketAnalysis | None:
    return _model_from_session(SessionKeys.TARGET_MARKET_ANALYSIS, TargetMarketAnalysis)


def _current_compatibility() -> CompatibilityReport | None:
    return _model_from_session(SessionKeys.COMPATIBILITY_REPORT, CompatibilityReport)


def _current_output_language() -> OutputLanguage | str:
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if raw_input:
        try:
            return CandidateInput.model_validate(raw_input).output_language
        except ValueError:
            pass
    return st.session_state.get(SessionKeys.OUTPUT_LANGUAGE, DEFAULT_OUTPUT_LANGUAGE)


def _current_generation_result(job_index: int) -> TargetedCVGenerationResult | None:
    raw = _dict_get(SessionKeys.TARGETED_CV_GENERATION_RESULTS, job_index)
    if not raw:
        return None
    try:
        return TargetedCVGenerationResult.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cv(job_index: int) -> TargetedCV | None:
    raw = _dict_get(SessionKeys.TARGETED_CVS, job_index)
    if not raw:
        return None
    try:
        return TargetedCV.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cvs() -> dict[int, TargetedCV]:
    output = {}
    raw = st.session_state.get(SessionKeys.TARGETED_CVS) or {}
    if not isinstance(raw, dict):
        return output
    for key, value in raw.items():
        if not value:
            continue
        try:
            output[int(key)] = TargetedCV.model_validate(value)
        except (TypeError, ValueError):
            continue
    return output


def _job_analysis_by_index(market: TargetMarketAnalysis | None, job_index: int) -> JobAnalysis | None:
    if market is None:
        return None
    return next((job for job in market.job_analyses if job.job_index == job_index), None)


def _job_compatibility_by_index(compatibility: CompatibilityReport | None, job_index: int) -> JobCompatibility | None:
    if compatibility is None:
        return None
    return next((job for job in compatibility.job_compatibilities if job.job_index == job_index), None)


def _model_from_session(key: str, model_class):
    raw = st.session_state.get(key)
    if not raw:
        return None
    try:
        return model_class.model_validate(raw)
    except ValueError:
        return None


def _dict_get(session_key: str, job_index: int) -> Any:
    raw = st.session_state.get(session_key) or {}
    if not isinstance(raw, dict):
        return None
    return raw.get(str(job_index)) or raw.get(job_index)


def _dict_set(session_key: str, job_index: int, value: Any) -> None:
    raw = st.session_state.get(session_key)
    if not isinstance(raw, dict):
        raw = {}
    if value is None:
        raw.pop(str(job_index), None)
        raw.pop(job_index, None)
    else:
        raw[str(job_index)] = value
    st.session_state[session_key] = raw


def _clear_targeted_cv_bytes(job_index: int) -> None:
    _dict_set(SessionKeys.TARGETED_CV_MARKDOWN_BYTES, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_DOCX_BYTES, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_PDF_BYTES, job_index, None)
    _dict_set(SessionKeys.TARGETED_CV_EXPORT_FINGERPRINTS, job_index, None)
    st.session_state[SessionKeys.TARGETED_CV_ZIP_BYTES] = None


def _clear_application_communication_for_job(job_index: int) -> None:
    for key in (
        SessionKeys.APPLICATION_COMMUNICATION_RESULTS,
        SessionKeys.APPLICATION_COMMUNICATION_KITS,
        SessionKeys.APPLICATION_COMMUNICATION_AUDITS,
        SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS,
        SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS,
        SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES,
        SessionKeys.APPLICATION_COMMUNICATION_EDIT_VALIDATIONS,
        SessionKeys.APPLICATION_COMMUNICATION_EXPORT_FINGERPRINTS,
        SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES,
        SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES,
        SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES,
        SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES,
    ):
        _dict_set(key, job_index, None)
    st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = None


def _targeted_cv_bytes_available(job_index: int) -> bool:
    return all(
        _dict_get(key, job_index)
        for key in (
            SessionKeys.TARGETED_CV_MARKDOWN_BYTES,
            SessionKeys.TARGETED_CV_DOCX_BYTES,
            SessionKeys.TARGETED_CV_PDF_BYTES,
        )
    )


def _export_fingerprint(targeted_cv: TargetedCV) -> str:
    payload = {
        "export_version": TARGETED_CV_EXPORT_VERSION,
        "targeted_cv": targeted_cv.model_dump(mode="json", exclude={"generated_at"}),
    }
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()
