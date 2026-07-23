"""Streamlit views for application communication kits."""

from __future__ import annotations

import streamlit as st

from components.application_communication_flow import (
    APPLICATION_COMMUNICATION_EXPORT_FAILURE_MESSAGE,
    APPLICATION_COMMUNICATION_EXPORT_SUCCESS_MESSAGE,
    APPLICATION_COMMUNICATION_MISSING_STAGES_MESSAGE,
    APPLICATION_COMMUNICATION_MISSING_TARGETED_CV_MESSAGE,
    APPLICATION_COMMUNICATION_REPROCESS_FAILURE_MESSAGE,
    APPLICATION_COMMUNICATION_SUCCESS_MESSAGE,
    build_application_communication_exports_from_session,
    run_all_application_communications_from_session,
    run_application_communication_from_session,
)
from exporters.application_communication_markdown_exporter import application_communication_download_filename
from exporters.application_communication_txt_exporter import application_communication_txt_download_filename
from exporters.application_communication_zip_exporter import APPLICATION_COMMUNICATION_ZIP_FILENAME
from schemas.application_communication_models import (
    ApplicationCommunicationAuditResult,
    ApplicationCommunicationEditValidationResult,
    ApplicationCommunicationGenerationResult,
    ApplicationCommunicationKit,
    CommunicationRedundancyAuditResult,
)
from schemas.compatibility_models import CompatibilityReport, JobCompatibility
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis, TargetMarketAnalysis
from schemas.targeted_cv_models import TargetedCV, TargetedCVAuditResult
from services.application_communication_edit_validation_service import build_application_communication_edit_state
from utils.constants import EMPTY_RESULT_MESSAGE
from utils.session import SessionKeys


def render_application_communication_tab() -> None:
    """Render per-vacancy application communication generation and editing."""
    st.markdown("### Kit de postulación por vacante")
    profile = _current_profile()
    market = _current_market_analysis()
    compatibility = _current_compatibility_report()
    if profile is None or market is None or compatibility is None:
        st.info(APPLICATION_COMMUNICATION_MISSING_STAGES_MESSAGE)
        return

    _render_summary(market)
    if st.button("Generar kits para todas las vacantes", key="application_communication_generate_all"):
        with st.status("Generando kits de postulación...", expanded=False) as status:
            results = run_all_application_communications_from_session(
                force=False,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            success_count = sum(1 for result in results if result.success)
            if success_count:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = f"{success_count} kit(s) de postulación generados correctamente."
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Kits de postulación generados.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = "No fue posible generar kits de postulación."
                status.update(label="No fue posible generar los kits.", state="error")

    if st.button("Preparar descargas de postulación", key="application_communication_export_all"):
        with st.status("Preparando descargas de postulación...", expanded=False) as status:
            export_result = build_application_communication_exports_from_session()
            if export_result["success"]:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = APPLICATION_COMMUNICATION_EXPORT_SUCCESS_MESSAGE
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Descargas de postulación listas.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = APPLICATION_COMMUNICATION_EXPORT_FAILURE_MESSAGE
                status.update(label="No fue posible preparar todas las descargas.", state="error")
                for error in export_result["errors"]:
                    st.error(error)

    for job in sorted(market.job_analyses, key=lambda item: item.job_index):
        job_compatibility = next(
            (item for item in compatibility.job_compatibilities if item.job_index == job.job_index),
            None,
        )
        _render_card(job, job_compatibility)


def render_application_communication_downloads_section() -> None:
    """Render communication downloads inside the global downloads tab."""
    st.markdown("#### Kits de postulación")
    kits = _current_kits()
    if not kits:
        st.caption("Los kits de postulación aparecerán aquí cuando se generen desde la pestaña Postulación.")
        return
    if st.button("Preparar descargas de postulación", key="downloads_application_communication_export_all"):
        export_result = build_application_communication_exports_from_session()
        if export_result["success"]:
            st.success(APPLICATION_COMMUNICATION_EXPORT_SUCCESS_MESSAGE)
        else:
            st.error(APPLICATION_COMMUNICATION_EXPORT_FAILURE_MESSAGE)
            for error in export_result["errors"]:
                st.caption(error)

    rows = []
    for index, kit in sorted(kits.items()):
        rows.append(
            {
                "Vacante": index,
                "Título": kit.target_job_title,
                "Markdown": _format_bytes(SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES, index),
                "TXT": _format_bytes(SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES, index),
                "DOCX": _format_bytes(SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES, index),
                "PDF": _format_bytes(SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES, index),
            }
        )
    st.table(rows)
    zip_bytes = st.session_state.get(SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES)
    if zip_bytes:
        st.download_button(
            "Descargar ZIP de kits de postulación",
            data=zip_bytes,
            file_name=APPLICATION_COMMUNICATION_ZIP_FILENAME,
            mime="application/zip",
            key="downloads_application_communication_zip",
        )
    for index, kit in sorted(kits.items()):
        _render_download_buttons(index, kit, key_prefix="downloads_application_communication")


def _render_summary(market: TargetMarketAnalysis) -> None:
    kits = _current_kits()
    audits = _current_audits()
    redundancy_audits = _current_redundancy_audits()
    targeted_cv_audits = _current_targeted_cv_audits()
    job_count = len(market.job_analyses)
    generated_count = len(kits)
    valid_count = sum(1 for audit in audits.values() if audit.passed)
    cv_count = sum(1 for audit in targeted_cv_audits.values() if audit.passed)
    warning_count = sum(
        1
        for audit in [*audits.values(), *redundancy_audits.values()]
        for finding in audit.findings
        if finding.severity == "warning"
    )
    columns = st.columns(4)
    columns[0].metric("Vacantes", job_count)
    columns[1].metric("CVs disponibles", cv_count)
    columns[2].metric("Kits generados", generated_count)
    columns[3].metric("Kits válidos", valid_count)
    if generated_count < job_count:
        st.caption(f"Pendientes: {job_count - generated_count}")
    if warning_count:
        st.caption(f"Advertencias de revisión: {warning_count}")


def _render_card(job: JobAnalysis, job_compatibility: JobCompatibility | None) -> None:
    kit = _current_kit(job.job_index)
    result = _current_generation_result(job.job_index)
    audit = _current_audit(job.job_index)
    redundancy = _current_redundancy_audit(job.job_index)
    validation = _current_edit_validation(job.job_index)
    targeted_cv = _current_targeted_cv(job.job_index)
    targeted_cv_audit = _current_targeted_cv_audit(job.job_index)
    company = job.company or "Empresa no especificada"
    with st.expander(f"Vacante {job.job_index} — {job.title} — {company}", expanded=kit is not None):
        columns = st.columns(4)
        columns[0].metric("Compatibilidad", f"{job_compatibility.compatibility_score:.0f}" if job_compatibility else "N/D")
        columns[1].metric("CV específico", "Válido" if targeted_cv_audit and targeted_cv_audit.passed else "Pendiente")
        columns[2].metric("Kit", "Generado" if kit else "Pendiente")
        columns[3].metric("Validación", "Válido" if audit and audit.passed else "Pendiente")

        if targeted_cv is None or targeted_cv_audit is None or not targeted_cv_audit.passed:
            st.info(APPLICATION_COMMUNICATION_MISSING_TARGETED_CV_MESSAGE)
            return

        button_label = "Regenerar kit" if kit else "Generar kit"
        if st.button(button_label, key=f"application_communication_generate_{job.job_index}"):
            with st.status(f"Generando kit para vacante {job.job_index}...", expanded=False) as status:
                result = run_application_communication_from_session(
                    job.job_index,
                    force=kit is not None,
                    preserve_previous_on_failure=True,
                    status_callback=lambda label: status.update(label=label, state="running"),
                )
                if result.success:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = APPLICATION_COMMUNICATION_SUCCESS_MESSAGE
                    st.session_state[SessionKeys.PROCESS_ERROR] = None
                    status.update(label="Kit de postulación listo.", state="complete")
                else:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                    st.session_state[SessionKeys.PROCESS_ERROR] = APPLICATION_COMMUNICATION_REPROCESS_FAILURE_MESSAGE if kit else result.user_message
                    status.update(label="No fue posible generar el kit.", state="error")

        result = _current_generation_result(job.job_index)
        _render_generation_message(result, kit is not None)
        kit = _current_kit(job.job_index)
        if kit is None:
            st.caption("El kit de postulación aparecerá aquí cuando se genere correctamente.")
            return

        _render_editor(kit)
        validation = _current_edit_validation(job.job_index)
        if validation:
            _render_validation(validation)
        _render_audit_details(kit, audit, redundancy)
        col_validate, col_export = st.columns(2)
        with col_validate:
            if st.button("Validar cambios", key=f"application_communication_validate_{job.job_index}", use_container_width=True):
                export_result = build_application_communication_exports_from_session(job.job_index)
                if export_result["success"]:
                    st.success("Los cambios del kit son válidos.")
                else:
                    st.error("Los cambios del kit requieren revisión antes de exportar.")
        with col_export:
            if st.button("Preparar descargas", key=f"application_communication_export_{job.job_index}", use_container_width=True):
                export_result = build_application_communication_exports_from_session(job.job_index)
                if export_result["success"]:
                    st.success(APPLICATION_COMMUNICATION_EXPORT_SUCCESS_MESSAGE)
                else:
                    st.error(APPLICATION_COMMUNICATION_EXPORT_FAILURE_MESSAGE)
                    for error in export_result["errors"]:
                        st.caption(error)
        _render_download_buttons(job.job_index, kit, key_prefix="application_communication")


def _render_generation_message(result: ApplicationCommunicationGenerationResult | None, has_kit: bool) -> None:
    if result is None:
        return
    if result.success:
        st.success(APPLICATION_COMMUNICATION_SUCCESS_MESSAGE)
        if result.reused_from_session:
            st.info("Se reutilizó el kit porque los insumos no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible generar el kit de postulación.")
        if result.error_category:
            st.caption(f"Categoría técnica: {result.error_category}")
        if has_kit:
            st.warning(APPLICATION_COMMUNICATION_REPROCESS_FAILURE_MESSAGE)
    for warning in result.warnings:
        st.warning(warning)


def _render_editor(kit: ApplicationCommunicationKit) -> None:
    edit_state = _ensure_edit_state(kit)
    st.markdown("#### Editor")
    letter_tab, recruiter_tab, email_tab, review_tab = st.tabs(["Carta", "Recruiter", "Correo", "Revisión"])
    with letter_tab:
        st.text_input(
            "Saludo de la carta",
            value=edit_state["cover_letter_greeting"],
            key=_edit_key(kit.target_job_index, "cover_letter_greeting"),
        )
        st.text_area(
            "Carta de presentación",
            value=edit_state["cover_letter_full_text"],
            key=_edit_key(kit.target_job_index, "cover_letter_full_text"),
            height=280,
        )
        st.text_input(
            "Cierre de la carta",
            value=edit_state["cover_letter_sign_off"],
            key=_edit_key(kit.target_job_index, "cover_letter_sign_off"),
        )
        st.caption(f"Palabras declaradas: {kit.cover_letter.word_count}")
        _render_simple_tags("Fortalezas usadas", kit.cover_letter.strengths_used)
        _render_simple_tags("Keywords usadas", kit.cover_letter.keywords_used)
    with recruiter_tab:
        st.text_area(
            "Mensaje para recruiter",
            value=edit_state["recruiter_message"],
            key=_edit_key(kit.target_job_index, "recruiter_message"),
            height=150,
        )
        st.caption(f"Caracteres declarados: {kit.recruiter_message.character_count}")
        st.caption(f"CTA: {kit.recruiter_message.call_to_action}")
    with email_tab:
        st.text_area(
            "Asuntos sugeridos",
            value="\n".join(edit_state["subject_options"]),
            key=_edit_key(kit.target_job_index, "subject_options"),
            height=90,
        )
        st.text_input(
            "Saludo del correo",
            value=edit_state["application_email_greeting"],
            key=_edit_key(kit.target_job_index, "application_email_greeting"),
        )
        st.text_area(
            "Correo de postulación",
            value=edit_state["application_email_full_text"],
            key=_edit_key(kit.target_job_index, "application_email_full_text"),
            height=240,
        )
        st.text_input(
            "Firma del correo",
            value=edit_state["application_email_sign_off"],
            key=_edit_key(kit.target_job_index, "application_email_sign_off"),
        )
        attachment_options = sorted(set(["CV adjunto", "Carta de presentación", *edit_state["attachments_mentioned"]]))
        st.multiselect(
            "Adjuntos mencionados",
            options=attachment_options,
            default=[value for value in edit_state["attachments_mentioned"] if value in attachment_options],
            key=_edit_key(kit.target_job_index, "attachments_mentioned"),
        )
        st.caption(f"Palabras declaradas: {kit.application_email.word_count}")
    with review_tab:
        _render_simple_tags("Llamadas a la acción", kit.calls_to_action)
        _render_simple_tags("Notas de personalización", kit.personalization_notes)
        _render_simple_tags("Riesgos o claims a revisar", kit.risks_or_claims_requiring_review)
    _sync_edit_state(kit, edit_state)


def _render_validation(validation: ApplicationCommunicationEditValidationResult) -> None:
    if validation.passed:
        st.success("Los cambios pasaron la validación local.")
    else:
        st.error("Los cambios no pasaron la validación local.")
    for finding in validation.findings:
        if finding.severity == "error":
            st.caption(f"error: {finding.path}: {finding.message}")
    for warning in validation.warnings:
        st.caption(f"warning: {warning}")


def _render_audit_details(
    kit: ApplicationCommunicationKit,
    audit: ApplicationCommunicationAuditResult | None,
    redundancy: CommunicationRedundancyAuditResult | None,
) -> None:
    with st.expander("Evidencia y revisión técnica"):
        st.caption(f"Carta: {kit.cover_letter.word_count} palabras")
        st.caption(f"Mensaje recruiter: {kit.recruiter_message.character_count} caracteres")
        st.caption(f"Correo: {kit.application_email.word_count} palabras")
        for label, claims in (
            ("Claims de carta", kit.cover_letter.claims),
            ("Claims de recruiter", kit.recruiter_message.claims),
            ("Claims de correo", kit.application_email.claims),
        ):
            if claims:
                st.markdown(f"##### {label}")
                for claim in claims:
                    st.caption(f"{claim.evidence_status}: {claim.text}")
        if audit and audit.findings:
            st.markdown("##### Hallazgos de comunicación")
            for finding in audit.findings:
                st.caption(f"{finding.severity}: {finding.path}: {finding.message}")
        if redundancy and redundancy.findings:
            st.markdown("##### Redundancia")
            for finding in redundancy.findings:
                st.caption(f"{finding.severity}: {finding.path}: {finding.message}")


def _render_download_buttons(index: int, kit: ApplicationCommunicationKit, *, key_prefix: str) -> None:
    markdown = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES, index)
    txt = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES, index)
    docx = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES, index)
    pdf = _dict_get(SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES, index)
    if not all([markdown, txt, docx, pdf]):
        st.caption("Prepara las descargas para habilitar los archivos de esta vacante.")
        return
    st.download_button(
        f"Vacante {index} - Postulación Markdown",
        data=markdown,
        file_name=application_communication_download_filename(kit, "md"),
        mime="text/markdown",
        key=f"{key_prefix}_md_{index}",
    )
    st.download_button(
        f"Vacante {index} - Postulación TXT",
        data=txt,
        file_name=application_communication_txt_download_filename(kit),
        mime="text/plain",
        key=f"{key_prefix}_txt_{index}",
    )
    st.download_button(
        f"Vacante {index} - Postulación DOCX",
        data=docx,
        file_name=application_communication_download_filename(kit, "docx"),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=f"{key_prefix}_docx_{index}",
    )
    st.download_button(
        f"Vacante {index} - Postulación PDF",
        data=pdf,
        file_name=application_communication_download_filename(kit, "pdf"),
        mime="application/pdf",
        key=f"{key_prefix}_pdf_{index}",
    )


def _ensure_edit_state(kit: ApplicationCommunicationKit) -> dict:
    fingerprints = st.session_state.get(SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS) or {}
    fingerprint = fingerprints.get(str(kit.target_job_index))
    edit_states = st.session_state.get(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES) or {}
    edit_state = edit_states.get(str(kit.target_job_index))
    if not edit_state or edit_state.get("_source_fingerprint") != fingerprint:
        edit_state = build_application_communication_edit_state(kit)
        edit_state["_source_fingerprint"] = fingerprint
        edit_states[str(kit.target_job_index)] = edit_state
        st.session_state[SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES] = edit_states
        _reset_edit_widgets(kit)
    return edit_state


def _sync_edit_state(kit: ApplicationCommunicationKit, edit_state: dict) -> None:
    current = {
        "edited": False,
        "_source_fingerprint": edit_state.get("_source_fingerprint"),
        "cover_letter_greeting": st.session_state.get(
            _edit_key(kit.target_job_index, "cover_letter_greeting"),
            edit_state["cover_letter_greeting"],
        ),
        "cover_letter_full_text": st.session_state.get(
            _edit_key(kit.target_job_index, "cover_letter_full_text"),
            edit_state["cover_letter_full_text"],
        ),
        "cover_letter_sign_off": st.session_state.get(
            _edit_key(kit.target_job_index, "cover_letter_sign_off"),
            edit_state["cover_letter_sign_off"],
        ),
        "recruiter_message": st.session_state.get(
            _edit_key(kit.target_job_index, "recruiter_message"),
            edit_state["recruiter_message"],
        ),
        "subject_options": _lines(
            st.session_state.get(_edit_key(kit.target_job_index, "subject_options"), "\n".join(edit_state["subject_options"]))
        ),
        "application_email_greeting": st.session_state.get(
            _edit_key(kit.target_job_index, "application_email_greeting"),
            edit_state["application_email_greeting"],
        ),
        "application_email_full_text": st.session_state.get(
            _edit_key(kit.target_job_index, "application_email_full_text"),
            edit_state["application_email_full_text"],
        ),
        "application_email_sign_off": st.session_state.get(
            _edit_key(kit.target_job_index, "application_email_sign_off"),
            edit_state["application_email_sign_off"],
        ),
        "attachments_mentioned": st.session_state.get(
            _edit_key(kit.target_job_index, "attachments_mentioned"),
            edit_state["attachments_mentioned"],
        ),
    }
    original = build_application_communication_edit_state(kit)
    current["edited"] = _state_without_metadata(current) != _state_without_metadata(original)
    edit_states = st.session_state.get(SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES) or {}
    previous = edit_states.get(str(kit.target_job_index))
    if isinstance(previous, dict) and _state_without_metadata(previous) != _state_without_metadata(current):
        _clear_bytes(kit.target_job_index)
    edit_states[str(kit.target_job_index)] = current
    st.session_state[SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES] = edit_states
    if current["edited"]:
        st.info("Kit editado por el usuario")


def _reset_edit_widgets(kit: ApplicationCommunicationKit) -> None:
    prefix = f"application_communication_edit_{kit.target_job_index}_"
    for key in list(st.session_state.keys()):
        if str(key).startswith(prefix):
            del st.session_state[key]


def _clear_bytes(job_index: int) -> None:
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES, job_index, None)
    _dict_set(SessionKeys.APPLICATION_COMMUNICATION_EXPORT_FINGERPRINTS, job_index, None)
    st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = None


def _render_simple_tags(title: str, values: list[str]) -> None:
    if values:
        st.caption(f"{title}: {', '.join(values)}")


def _state_without_metadata(state: dict) -> dict:
    return {key: value for key, value in state.items() if key not in {"edited", "_source_fingerprint"}}


def _edit_key(job_index: int, name: str) -> str:
    return f"application_communication_edit_{job_index}_{name}"


def _lines(value: object) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _current_profile() -> CandidateProfessionalProfile | None:
    raw = st.session_state.get(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE)
    return _model(raw, CandidateProfessionalProfile)


def _current_market_analysis() -> TargetMarketAnalysis | None:
    raw = st.session_state.get(SessionKeys.TARGET_MARKET_ANALYSIS)
    return _model(raw, TargetMarketAnalysis)


def _current_compatibility_report() -> CompatibilityReport | None:
    raw = st.session_state.get(SessionKeys.COMPATIBILITY_REPORT)
    return _model(raw, CompatibilityReport)


def _current_generation_result(job_index: int) -> ApplicationCommunicationGenerationResult | None:
    return _model(_dict_get(SessionKeys.APPLICATION_COMMUNICATION_RESULTS, job_index), ApplicationCommunicationGenerationResult)


def _current_kit(job_index: int) -> ApplicationCommunicationKit | None:
    return _model(_dict_get(SessionKeys.APPLICATION_COMMUNICATION_KITS, job_index), ApplicationCommunicationKit)


def _current_kits() -> dict[int, ApplicationCommunicationKit]:
    return _model_dict(SessionKeys.APPLICATION_COMMUNICATION_KITS, ApplicationCommunicationKit)


def _current_audit(job_index: int) -> ApplicationCommunicationAuditResult | None:
    return _model(_dict_get(SessionKeys.APPLICATION_COMMUNICATION_AUDITS, job_index), ApplicationCommunicationAuditResult)


def _current_audits() -> dict[int, ApplicationCommunicationAuditResult]:
    return _model_dict(SessionKeys.APPLICATION_COMMUNICATION_AUDITS, ApplicationCommunicationAuditResult)


def _current_redundancy_audit(job_index: int) -> CommunicationRedundancyAuditResult | None:
    return _model(
        _dict_get(SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS, job_index),
        CommunicationRedundancyAuditResult,
    )


def _current_redundancy_audits() -> dict[int, CommunicationRedundancyAuditResult]:
    return _model_dict(SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS, CommunicationRedundancyAuditResult)


def _current_edit_validation(job_index: int) -> ApplicationCommunicationEditValidationResult | None:
    return _model(
        _dict_get(SessionKeys.APPLICATION_COMMUNICATION_EDIT_VALIDATIONS, job_index),
        ApplicationCommunicationEditValidationResult,
    )


def _current_targeted_cv(job_index: int) -> TargetedCV | None:
    return _model(_dict_get(SessionKeys.TARGETED_CVS, job_index), TargetedCV)


def _current_targeted_cv_audit(job_index: int) -> TargetedCVAuditResult | None:
    return _model(_dict_get(SessionKeys.TARGETED_CV_AUDITS, job_index), TargetedCVAuditResult)


def _current_targeted_cv_audits() -> dict[int, TargetedCVAuditResult]:
    return _model_dict(SessionKeys.TARGETED_CV_AUDITS, TargetedCVAuditResult)


def _model(raw, model_class):
    if not raw:
        return None
    try:
        return model_class.model_validate(raw)
    except ValueError:
        return None


def _model_dict(session_key: str, model_class) -> dict[int, object]:
    output = {}
    raw = st.session_state.get(session_key) or {}
    if not isinstance(raw, dict):
        return output
    for key, value in raw.items():
        if not value:
            continue
        try:
            output[int(key)] = model_class.model_validate(value)
        except (TypeError, ValueError):
            continue
    return output


def _dict_get(session_key: str, job_index: int) -> object | None:
    raw = st.session_state.get(session_key) or {}
    if not isinstance(raw, dict):
        return None
    return raw.get(str(job_index)) or raw.get(job_index)


def _dict_set(session_key: str, job_index: int, value: object | None) -> None:
    raw = st.session_state.get(session_key)
    if not isinstance(raw, dict):
        raw = {}
    if value is None:
        raw.pop(str(job_index), None)
        raw.pop(job_index, None)
    else:
        raw[str(job_index)] = value
    st.session_state[session_key] = raw


def _format_bytes(session_key: str, job_index: int) -> str:
    data = _dict_get(session_key, job_index) or b""
    return f"{len(data) / 1024:.1f} KB" if data else "Pendiente"
