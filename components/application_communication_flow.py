"""Streamlit session orchestration for per-vacancy application communications."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from exporters.application_communication_docx_exporter import ApplicationCommunicationDocxExporter
from exporters.application_communication_markdown_exporter import ApplicationCommunicationMarkdownExporter
from exporters.application_communication_pdf_exporter import ApplicationCommunicationPDFExporter
from exporters.application_communication_txt_exporter import ApplicationCommunicationTxtExporter
from exporters.application_communication_zip_exporter import ApplicationCommunicationZipExporter
from schemas.application_communication_models import (
    APPLICATION_COMMUNICATION_EXPORT_VERSION,
    ApplicationCommunicationAuditResult,
    ApplicationCommunicationEditValidationResult,
    ApplicationCommunicationGenerationResult,
    ApplicationCommunicationKit,
    CommunicationRedundancyAuditResult,
)
from schemas.compatibility_models import CompatibilityReport, JobCompatibility
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput
from schemas.market_models import JobAnalysis, TargetMarketAnalysis
from schemas.targeted_cv_models import TargetedCV, TargetedCVAuditResult
from services.application_communication_audit_service import audit_application_communication_kit
from services.application_communication_edit_validation_service import (
    apply_application_communication_edit_state,
    build_application_communication_edit_state,
    validate_application_communication_edits,
)
from services.application_communication_pipeline import (
    APPLICATION_COMMUNICATION_MISSING_TARGETED_CV_MESSAGE,
    ApplicationCommunicationGenerationRun,
    run_application_communication_generation_pipeline,
)
from services.communication_redundancy_audit_service import audit_communication_redundancy
from services.export_audit_service import ExportAuditService
from utils.constants import DEFAULT_OUTPUT_LANGUAGE
from utils.session import SessionKeys

APPLICATION_COMMUNICATION_SUCCESS_MESSAGE = "El kit de postulación fue generado y validado correctamente."
APPLICATION_COMMUNICATION_REPROCESS_FAILURE_MESSAGE = (
    "El nuevo intento de generación del kit de postulación falló. Se conserva el último kit válido de esta sesión."
)
APPLICATION_COMMUNICATION_MISSING_STAGES_MESSAGE = (
    "Para generar comunicaciones por vacante se necesita primero un perfil profesional válido, "
    "un análisis válido de vacantes, compatibilidad válida y CVs específicos validados."
)
APPLICATION_COMMUNICATION_EXPORT_FAILURE_MESSAGE = (
    "El kit fue validado, pero uno o más archivos generados no superaron la auditoría local de exportación."
)
APPLICATION_COMMUNICATION_EXPORT_SUCCESS_MESSAGE = "Los archivos de postulación quedaron listos para descargar."


def run_application_communication_from_session(
    job_index: int,
    *,
    force: bool = False,
    preserve_previous_on_failure: bool = True,
    status_callback: Callable[[str], None] | None = None,
) -> ApplicationCommunicationGenerationResult:
    """Run communication kit generation for one job from session state."""
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    output_language = _current_output_language()
    job_analysis = _job_analysis_by_index(market, job_index)
    job_compatibility = _job_compatibility_by_index(compatibility, job_index)
    targeted_cv = _current_targeted_cv(job_index)
    targeted_cv_audit = _current_targeted_cv_audit(job_index)
    if profile is None or market is None or compatibility is None or job_analysis is None or job_compatibility is None:
        result = ApplicationCommunicationGenerationResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=APPLICATION_COMMUNICATION_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        _store_generation_result(job_index, result, None, preserve_previous_on_failure=False)
        return result
    if targeted_cv is None or targeted_cv_audit is None or not targeted_cv_audit.passed:
        result = ApplicationCommunicationGenerationResult(
            success=False,
            error_category="missing_targeted_cv",
            user_message=APPLICATION_COMMUNICATION_MISSING_TARGETED_CV_MESSAGE,
            retryable=False,
        )
        _store_generation_result(job_index, result, None, preserve_previous_on_failure=preserve_previous_on_failure)
        return result

    existing_result = _current_generation_result(job_index)
    existing_fingerprint = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS, job_index)
    run = run_application_communication_generation_pipeline(
        profile,
        job_analysis,
        job_compatibility,
        targeted_cv,
        output_language,
        existing_result=existing_result,
        existing_fingerprint=existing_fingerprint,
        force=force,
        status_callback=status_callback,
    )
    _store_generation_result(job_index, run.result, run, preserve_previous_on_failure=preserve_previous_on_failure)
    return run.result


def run_all_application_communications_from_session(
    *,
    force: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> list[ApplicationCommunicationGenerationResult]:
    """Generate communication kits sequentially for all analyzed jobs with validated CVs."""
    market = _current_market()
    if market is None:
        result = ApplicationCommunicationGenerationResult(
            success=False,
            error_category="missing_previous_stages",
            user_message=APPLICATION_COMMUNICATION_MISSING_STAGES_MESSAGE,
            retryable=False,
        )
        return [result]
    results = []
    for job in sorted(market.job_analyses, key=lambda item: item.job_index):
        if status_callback:
            status_callback(f"Generando comunicación para vacante {job.job_index} de {len(market.job_analyses)}...")
        results.append(
            run_application_communication_from_session(
                job.job_index,
                force=force,
                preserve_previous_on_failure=True,
                status_callback=status_callback,
            )
        )
    return results


def build_application_communication_exports_from_session(job_index: int | None = None) -> dict[str, Any]:
    """Validate edits, export communication bytes and store them in session."""
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    if profile is None or market is None or compatibility is None:
        return {"success": False, "errors": [APPLICATION_COMMUNICATION_MISSING_STAGES_MESSAGE], "exported_indices": []}

    indices = [job_index] if job_index is not None else sorted(_current_kits().keys())
    exported_indices: list[int] = []
    errors: list[str] = []
    audits: dict[int, ApplicationCommunicationAuditResult] = {}
    redundancy_audits: dict[int, CommunicationRedundancyAuditResult] = {}
    validations: dict[int, ApplicationCommunicationEditValidationResult] = {}

    for index in indices:
        kit = _current_kit(index)
        targeted_cv = _current_targeted_cv(index)
        job_analysis = _job_analysis_by_index(market, index)
        job_compatibility = _job_compatibility_by_index(compatibility, index)
        if kit is None or targeted_cv is None or job_analysis is None or job_compatibility is None:
            errors.append(f"Vacante {index}: no existe un kit de postulación generado y válido.")
            continue

        edit_state = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES, index)
        edited_kit = apply_application_communication_edit_state(kit, edit_state)
        validation = validate_application_communication_edits(kit, profile, job_analysis, job_compatibility, targeted_cv, edit_state)
        validations[index] = validation
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EDIT_VALIDATIONS, index, validation.model_dump())
        if not validation.passed:
            errors.append(f"Vacante {index}: los cambios de postulación no pasaron validación local.")
            _clear_application_communication_bytes(index)
            continue

        audit = audit_application_communication_kit(edited_kit, profile, job_analysis, job_compatibility, targeted_cv)
        redundancy = audit_communication_redundancy(edited_kit, targeted_cv)
        audits[index] = audit
        redundancy_audits[index] = redundancy
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_AUDITS, index, audit.model_dump())
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS, index, redundancy.model_dump())
        if not audit.passed or not redundancy.passed:
            errors.append(f"Vacante {index}: el kit editado no pasó auditoría local.")
            _clear_application_communication_bytes(index)
            continue

        export_fingerprint = _export_fingerprint(edited_kit)
        if (
            _dict_get(SessionKeys.APPLICATION_COMMUNICATION_EXPORT_FINGERPRINTS, index) == export_fingerprint
            and _application_communication_bytes_available(index)
        ):
            exported_indices.append(index)
            continue

        markdown = ApplicationCommunicationMarkdownExporter().export(edited_kit)
        txt = ApplicationCommunicationTxtExporter().export(edited_kit)
        docx = ApplicationCommunicationDocxExporter().export(edited_kit)
        pdf = ApplicationCommunicationPDFExporter().export(edited_kit)
        export_audit = ExportAuditService().audit_application_communication_all(
            {"markdown": markdown, "txt": txt, "docx": docx, "pdf": pdf, "zip": b""}
        )
        non_zip_findings = [finding for finding in export_audit.findings if not finding.startswith("application_communication_zip")]
        if non_zip_findings:
            errors.extend(non_zip_findings)
            _clear_application_communication_bytes(index)
            continue
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES, index, markdown)
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES, index, txt)
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES, index, docx)
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES, index, pdf)
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EXPORT_FINGERPRINTS, index, export_fingerprint)
        exported_indices.append(index)

    if exported_indices:
        all_kits, all_audits, all_redundancy, all_validations = _edited_kits_for_zip(profile, market, compatibility)
        zip_bytes = ApplicationCommunicationZipExporter().export(
            all_kits,
            audits=all_audits,
            redundancy_audits=all_redundancy,
            edit_validations=all_validations,
        )
        zip_audit = ExportAuditService().audit_application_communication_zip(zip_bytes)
        if zip_audit.passed:
            st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = zip_bytes
        else:
            st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = None
            errors.extend(zip_audit.findings)

    return {"success": bool(exported_indices) and not errors, "errors": errors, "exported_indices": exported_indices}


def current_application_communication_for_export(job_index: int) -> ApplicationCommunicationKit | None:
    """Return the edited communication kit for one job if available."""
    kit = _current_kit(job_index)
    if kit is None:
        return None
    return apply_application_communication_edit_state(
        kit,
        _dict_get(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES, job_index),
    )


def _store_generation_result(
    job_index: int,
    result: ApplicationCommunicationGenerationResult,
    run: ApplicationCommunicationGenerationRun | None,
    *,
    preserve_previous_on_failure: bool,
) -> None:
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_RESULTS, job_index, result.model_dump())
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_LAST_RUNS, job_index, datetime.now().isoformat(timespec="seconds"))
    if result.success and result.communication_kit is not None:
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_KITS, job_index, result.communication_kit.model_dump())
        if run and run.fingerprint:
            _dict_set(SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS, job_index, run.fingerprint)
        if run and run.audit:
            _dict_set(SessionKeys.APPLICATION_COMMUNICATION_AUDITS, job_index, run.audit.model_dump())
        if run and run.redundancy_audit:
            _dict_set(SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS, job_index, run.redundancy_audit.model_dump())
        edit_state = build_application_communication_edit_state(result.communication_kit)
        edit_state["_source_fingerprint"] = run.fingerprint if run else None
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES, job_index, edit_state)
        _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EDIT_VALIDATIONS, job_index, None)
        _clear_application_communication_bytes(job_index)
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = None
        return

    if preserve_previous_on_failure and _dict_get(SessionKeys.APPLICATION_COMMUNICATION_KITS, job_index):
        st.session_state[SessionKeys.PROCESS_ERROR] = APPLICATION_COMMUNICATION_REPROCESS_FAILURE_MESSAGE
        return

    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_KITS, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_AUDITS, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EDIT_VALIDATIONS, job_index, None)
    _clear_application_communication_bytes(job_index)


def _edited_kits_for_zip(
    profile: CandidateProfessionalProfile,
    market: TargetMarketAnalysis,
    compatibility: CompatibilityReport,
) -> tuple[
    list[ApplicationCommunicationKit],
    dict[int, ApplicationCommunicationAuditResult],
    dict[int, CommunicationRedundancyAuditResult],
    dict[int, ApplicationCommunicationEditValidationResult],
]:
    kits: list[ApplicationCommunicationKit] = []
    audits: dict[int, ApplicationCommunicationAuditResult] = {}
    redundancy_audits: dict[int, CommunicationRedundancyAuditResult] = {}
    validations: dict[int, ApplicationCommunicationEditValidationResult] = {}
    for index in sorted(_current_kits()):
        kit = _current_kit(index)
        targeted_cv = _current_targeted_cv(index)
        job_analysis = _job_analysis_by_index(market, index)
        job_compatibility = _job_compatibility_by_index(compatibility, index)
        if kit is None or targeted_cv is None or job_analysis is None or job_compatibility is None:
            continue
        edit_state = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES, index)
        edited = apply_application_communication_edit_state(kit, edit_state)
        validation = validate_application_communication_edits(kit, profile, job_analysis, job_compatibility, targeted_cv, edit_state)
        audit = audit_application_communication_kit(edited, profile, job_analysis, job_compatibility, targeted_cv)
        redundancy = audit_communication_redundancy(edited, targeted_cv)
        if validation.passed and audit.passed and redundancy.passed:
            kits.append(edited)
            audits[index] = audit
            redundancy_audits[index] = redundancy
            validations[index] = validation
    return kits, audits, redundancy_audits, validations


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


def _current_generation_result(job_index: int) -> ApplicationCommunicationGenerationResult | None:
    raw = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_RESULTS, job_index)
    if not raw:
        return None
    try:
        return ApplicationCommunicationGenerationResult.model_validate(raw)
    except ValueError:
        return None


def _current_kit(job_index: int) -> ApplicationCommunicationKit | None:
    raw = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_KITS, job_index)
    if not raw:
        return None
    try:
        return ApplicationCommunicationKit.model_validate(raw)
    except ValueError:
        return None


def _current_kits() -> dict[int, ApplicationCommunicationKit]:
    output = {}
    raw = st.session_state.get(SessionKeys.APPLICATION_COMMUNICATION_KITS) or {}
    if not isinstance(raw, dict):
        return output
    for key, value in raw.items():
        if not value:
            continue
        try:
            output[int(key)] = ApplicationCommunicationKit.model_validate(value)
        except (TypeError, ValueError):
            continue
    return output


def _current_targeted_cv(job_index: int) -> TargetedCV | None:
    raw = _dict_get(SessionKeys.TARGETED_CVS, job_index)
    if not raw:
        return None
    try:
        return TargetedCV.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cv_audit(job_index: int) -> TargetedCVAuditResult | None:
    raw = _dict_get(SessionKeys.TARGETED_CV_AUDITS, job_index)
    if not raw:
        return None
    try:
        return TargetedCVAuditResult.model_validate(raw)
    except ValueError:
        return None


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


def _clear_application_communication_bytes(job_index: int) -> None:
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EXPORT_FINGERPRINTS, job_index, None)
    st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = None


def _application_communication_bytes_available(job_index: int) -> bool:
    return all(
        _dict_get(key, job_index)
        for key in (
            SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES,
            SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES,
            SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES,
            SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES,
        )
    )


def _export_fingerprint(kit: ApplicationCommunicationKit) -> str:
    payload = {
        "export_version": APPLICATION_COMMUNICATION_EXPORT_VERSION,
        "communication_kit": kit.model_dump(mode="json", exclude={"generated_at"}),
    }
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()
