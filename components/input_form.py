"""Input form sections for the Astrogato Vector pilot."""

from __future__ import annotations

import streamlit as st

from components.candidate_extraction_flow import (
    EXTRACTION_SUCCESS_MESSAGE,
    run_candidate_extraction_from_session,
)
from components.compatibility_flow import COMPATIBILITY_SUCCESS_MESSAGE, run_compatibility_from_session
from components.final_audit_flow import run_final_audit_from_session
from components.job_analysis_flow import JOB_ANALYSIS_SUCCESS_MESSAGE, run_job_analysis_from_session
from components.linkedin_profile_flow import (
    LINKEDIN_PROFILE_SUCCESS_MESSAGE,
    run_linkedin_profile_generation_from_session,
)
from components.validation_views import (
    render_cv_diagnostic,
    render_input_summary,
    render_link_diagnostics,
    render_validation_messages,
)
from schemas.job_analysis_models import JobAnalysisResult
from services.candidate_input_service import prepare_candidate_input
from services.final_audit_service import FINAL_AUDIT_SUCCESS_MESSAGE
from services.input_resolution_service import resolve_all_inputs
from utils.constants import (
    DEFAULT_OUTPUT_LANGUAGE,
    FILE_UPLOAD_HELP,
    LANGUAGE_LABELS,
    LINKEDIN_HELP,
    MAX_JOB_POSTINGS,
    MIN_JOB_POSTINGS,
    OUTPUT_LANGUAGES,
    UPLOAD_TYPES,
)
from utils.session import (
    SessionKeys,
    add_job_posting,
    clear_candidate_extraction_state,
    clear_compatibility_state,
    clear_final_audit_state,
    clear_job_analysis_state,
    clear_linkedin_profile_generation_state,
    clear_processing_state,
    get_cv_file_uploader_key,
    get_job_field_key,
    remove_job_posting,
    request_clear_session_state,
    sync_cv_file_metadata,
)
from utils.validators import JobFormInput, ValidationMessage, validate_complete_form


def render_input_form() -> None:
    """Render all user inputs and primary actions."""
    render_cv_section()
    render_linkedin_section()
    render_jobs_section()
    render_language_section()
    render_primary_actions()
    render_form_feedback()


def render_cv_section() -> None:
    """Render CV text and file inputs."""
    with st.container(border=True):
        st.markdown('<div class="av-section-title">1. Currículum</div>', unsafe_allow_html=True)
        st.caption("Obligatorio: pega el texto del CV o carga un archivo DOCX/PDF.")
        text_tab, file_tab = st.tabs(["Pegar texto", "Cargar archivo"])

        with text_tab:
            st.text_area(
                "Contenido del CV",
                key=SessionKeys.CV_TEXT,
                placeholder="Pega aquí el contenido de tu CV sin formato.",
                height=220,
                label_visibility="collapsed",
            )

        with file_tab:
            uploaded_file = st.file_uploader(
                "Archivo de CV",
                type=UPLOAD_TYPES,
                key=get_cv_file_uploader_key(),
                label_visibility="collapsed",
            )
            _sync_current_cv_file(uploaded_file)
            if uploaded_file is not None:
                st.caption(f"Archivo cargado: {uploaded_file.name}")
            st.caption(FILE_UPLOAD_HELP)

        if st.session_state[SessionKeys.CV_TEXT].strip() and uploaded_file is not None:
            st.info(
                "Se utilizará el texto pegado como fuente principal. El archivo permanecerá disponible como referencia."
            )


def render_linkedin_section() -> None:
    """Render optional LinkedIn profile inputs."""
    with st.container(border=True):
        st.markdown(
            '<div class="av-section-title">2. Perfil de LinkedIn — opcional</div>',
            unsafe_allow_html=True,
        )
        st.caption(LINKEDIN_HELP)
        st.text_area(
            "Texto del perfil de LinkedIn",
            key=SessionKeys.LINKEDIN_TEXT,
            placeholder="Pega aquí el texto público de tu perfil de LinkedIn.",
            height=140,
        )
        st.text_input(
            "Enlace del perfil de LinkedIn",
            key=SessionKeys.LINKEDIN_URL,
            placeholder="https://www.linkedin.com/in/tu-perfil",
        )

        linkedin_text = st.session_state[SessionKeys.LINKEDIN_TEXT].strip()
        linkedin_url = st.session_state[SessionKeys.LINKEDIN_URL].strip()
        if linkedin_text and linkedin_url:
            st.info("Se utilizará el texto pegado como fuente principal.")
        elif not linkedin_text and not linkedin_url:
            st.caption(
                "No proporcionaste un perfil actual. Se generará una propuesta desde cero en un incremento posterior."
            )


def render_jobs_section() -> None:
    """Render dynamic job posting inputs."""
    with st.container(border=True):
        st.markdown('<div class="av-section-title">3. Vacantes objetivo</div>', unsafe_allow_html=True)
        job_count = int(st.session_state[SessionKeys.JOB_COUNT])
        st.caption(f"Vacantes capturadas: {job_count} de {MAX_JOB_POSTINGS}")
        st.caption(
            f"Agrega entre {MIN_JOB_POSTINGS} y {MAX_JOB_POSTINGS} vacantes. "
            "Cada una requiere título y descripción o enlace."
        )

        for index in range(job_count):
            render_job_posting(index)
            if index < job_count - 1:
                st.divider()

        add_disabled = job_count >= MAX_JOB_POSTINGS
        remove_disabled = job_count <= MIN_JOB_POSTINGS

        add_col, remove_col = st.columns([1, 1])
        with add_col:
            st.button(
                "Agregar vacante",
                on_click=add_job_posting,
                disabled=add_disabled,
                use_container_width=True,
            )
        with remove_col:
            st.button(
                "Eliminar última vacante",
                on_click=remove_job_posting,
                disabled=remove_disabled,
                use_container_width=True,
            )


def render_job_posting(index: int) -> None:
    """Render one job posting block."""
    number = index + 1
    st.markdown(f"**Vacante {number}**")
    title_col, company_col = st.columns([1, 1])

    with title_col:
        st.text_input(
            "Título o nombre del puesto (obligatorio)",
            key=get_job_field_key(index, "title"),
            placeholder="Ej. Product Manager",
        )
    with company_col:
        st.text_input(
            "Empresa opcional",
            key=get_job_field_key(index, "company"),
            placeholder="Ej. Empresa objetivo",
        )

    st.text_area(
        "Descripción",
        key=get_job_field_key(index, "description"),
        placeholder="Pega aquí la descripción de la vacante.",
        height=130,
    )
    st.text_input(
        "Enlace opcional",
        key=get_job_field_key(index, "url"),
        placeholder="https://...",
    )

    description = st.session_state[get_job_field_key(index, "description")].strip()
    url = st.session_state[get_job_field_key(index, "url")].strip()
    if description and url:
        st.caption("Se utilizará la descripción pegada como fuente principal.")


def render_language_section() -> None:
    """Render output language selector."""
    with st.container(border=True):
        st.markdown('<div class="av-section-title">4. Idioma de salida</div>', unsafe_allow_html=True)
        st.radio(
            "Selecciona el idioma de salida",
            options=OUTPUT_LANGUAGES,
            format_func=lambda value: LANGUAGE_LABELS[value],
            key=SessionKeys.OUTPUT_LANGUAGE,
            horizontal=True,
            label_visibility="collapsed",
        )


def render_primary_actions() -> None:
    """Render process and clear actions."""
    consent_accepted = bool(st.session_state[SessionKeys.CONSENT_ACCEPTED])
    process_col, clear_col = st.columns([1, 1])

    with process_col:
        process_clicked = st.button(
            "Procesar",
            type="primary",
            disabled=not consent_accepted,
            use_container_width=True,
        )
        if not consent_accepted:
            st.caption("Acepta el aviso para habilitar el procesamiento.")
    with clear_col:
        st.button("Limpiar", on_click=request_clear_session_state, use_container_width=True)

    if process_clicked:
        process_current_form()


def process_current_form() -> None:
    """Validate current state and prepare normalized input for future processing."""
    clear_processing_state()
    form_state = capture_form_state()
    status_label = _status_label_for_form_state(form_state)

    with st.status("Validando entradas...", expanded=False) as status:
        result = validate_complete_form(**_validation_state(form_state))
        messages = list(result.messages)

        if not result.is_valid:
            clear_candidate_extraction_state()
            clear_job_analysis_state()
            clear_compatibility_state()
            clear_linkedin_profile_generation_state()
            clear_final_audit_state()
            st.session_state[SessionKeys.VALIDATION_MESSAGES] = messages
            status.update(label="Corrige los campos señalados.", state="error")
            return

        status.update(label=status_label, state="running")
        preparation = prepare_candidate_input(**_preparation_state(form_state))
        messages.extend(preparation.messages)
        st.session_state[SessionKeys.VALIDATION_MESSAGES] = messages

        st.session_state[SessionKeys.CV_PARSE_SUMMARY] = (
            preparation.cv_summary.model_dump() if preparation.cv_summary else None
        )
        st.session_state[SessionKeys.CV_PARSE_RESULT] = (
            preparation.cv_parse_result.model_dump() if preparation.cv_parse_result else None
        )
        st.session_state[SessionKeys.CV_PREVIEW] = preparation.cv_preview

        if not preparation.is_valid:
            clear_candidate_extraction_state()
            clear_job_analysis_state()
            clear_compatibility_state()
            clear_linkedin_profile_generation_state()
            clear_final_audit_state()
            st.session_state[SessionKeys.CV_PARSE_RESULT] = (
                preparation.cv_parse_result.model_dump() if preparation.cv_parse_result else None
            )
            status.update(label="No fue posible preparar el CV.", state="error")
            return

        resolution = resolve_all_inputs(
            preparation,
            linkedin_text=form_state["linkedin_text"],
            linkedin_url=form_state["linkedin_url"],
            jobs=form_state["jobs"],
            output_language=form_state["output_language"],
            status_callback=lambda label: status.update(label=label, state="running"),
        )
        messages.extend(resolution.messages)
        messages = _dedupe_messages(messages)
        st.session_state[SessionKeys.VALIDATION_MESSAGES] = messages
        st.session_state[SessionKeys.LINKEDIN_LINK_SUMMARY] = resolution.linkedin_diagnostic
        st.session_state[SessionKeys.JOB_LINK_SUMMARIES] = resolution.job_diagnostics
        st.session_state[SessionKeys.LINK_ERROR] = resolution.link_error
        st.session_state[SessionKeys.FAILED_LINK_INDEX] = resolution.failed_link_index
        st.session_state[SessionKeys.LINK_PREVIEWS] = resolution.link_previews
        st.session_state[SessionKeys.RECOVERED_LINK_TEXTS] = resolution.recovered_link_texts
        st.session_state[SessionKeys.LINK_READING_COMPLETED] = resolution.link_reading_completed

        if not resolution.is_valid or resolution.candidate_input is None:
            clear_candidate_extraction_state()
            clear_job_analysis_state()
            clear_compatibility_state()
            clear_linkedin_profile_generation_state()
            clear_final_audit_state()
            st.session_state[SessionKeys.PROCESS_ERROR] = (
                "No fue posible completar la lectura de todos los enlaces necesarios."
            )
            status.update(label="No fue posible leer un enlace obligatorio.", state="error")
            return

        validated_input = resolution.candidate_input.model_dump()
        st.session_state[SessionKeys.VALIDATED_INPUT] = validated_input
        st.session_state[SessionKeys.INPUT_SUMMARY] = validated_input
        st.session_state[SessionKeys.HAS_PROCESSED] = True
        st.info(
            "El CV y, cuando exista, el perfil de LinkedIn serán enviados al proveedor de inteligencia "
            "artificial para extraer información profesional estructurada."
        )
        extraction_result = run_candidate_extraction_from_session(
            status_callback=lambda label: status.update(label=label, state="running"),
        )
        if extraction_result.success:
            st.info(
                "Las descripciones de las vacantes serán enviadas al proveedor de inteligencia artificial "
                "para analizar requisitos, responsabilidades y lenguaje del mercado. Esta llamada no incluye "
                "CV ni perfil de LinkedIn."
            )
            job_result = run_job_analysis_from_session(
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if job_result.success:
                compatibility_result = run_compatibility_from_session(
                    status_callback=lambda label: status.update(label=label, state="running"),
                )
                profile_generation_result = run_linkedin_profile_generation_from_session(
                    status_callback=lambda label: status.update(label=label, state="running"),
                )
                if not profile_generation_result.success:
                    clear_final_audit_state()
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = (
                        f"{EXTRACTION_SUCCESS_MESSAGE}\n\n{JOB_ANALYSIS_SUCCESS_MESSAGE}"
                        + (f"\n\n{COMPATIBILITY_SUCCESS_MESSAGE}" if compatibility_result.success else "")
                    )
                    st.session_state[SessionKeys.PROCESS_ERROR] = (
                        profile_generation_result.user_message
                        or "No fue posible generar el perfil optimizado de LinkedIn."
                    )
                    status.update(label="No fue posible generar el perfil de LinkedIn.", state="error")
                    return
                final_audit_result = None
                if compatibility_result.success:
                    final_audit_result = run_final_audit_from_session(
                        status_callback=lambda label: status.update(label=label, state="running"),
                    )
                    if not final_audit_result.success:
                        st.session_state[SessionKeys.PROCESS_MESSAGE] = (
                            f"{EXTRACTION_SUCCESS_MESSAGE}\n\n{JOB_ANALYSIS_SUCCESS_MESSAGE}\n\n"
                            f"{COMPATIBILITY_SUCCESS_MESSAGE}\n\n{LINKEDIN_PROFILE_SUCCESS_MESSAGE}"
                        )
                        st.session_state[SessionKeys.PROCESS_ERROR] = (
                            final_audit_result.user_message
                            or "No fue posible calcular la auditoría integral de posicionamiento."
                        )
                        status.update(label="LinkedIn y compatibilidad generados; auditoría pendiente.", state="error")
                        return
                else:
                    clear_final_audit_state()
                reused_message = None
                if (
                    extraction_result.reused_from_session
                    and job_result.reused_from_session
                    and compatibility_result.reused_from_session
                    and profile_generation_result.reused_from_session
                    and final_audit_result is not None
                    and final_audit_result.reused_from_session
                ):
                    reused_message = "Se reutilizaron el perfil profesional, el mercado objetivo, la compatibilidad, el perfil de LinkedIn y la auditoría integral porque las fuentes no cambiaron."
                elif extraction_result.reused_from_session:
                    reused_message = "Se reutilizó el perfil profesional porque las fuentes del candidato no cambiaron."
                elif job_result.reused_from_session:
                    reused_message = "Se reutilizó el análisis de vacantes porque las descripciones no cambiaron."
                elif compatibility_result.reused_from_session:
                    reused_message = "Se reutilizó el análisis de compatibilidad porque la evidencia, las vacantes y la metodología no cambiaron."
                elif profile_generation_result.reused_from_session:
                    reused_message = "Se reutilizó el perfil de LinkedIn generado porque la evidencia y las vacantes no cambiaron."
                elif final_audit_result is not None and final_audit_result.reused_from_session:
                    reused_message = "Se reutilizó la auditoría integral porque los resultados estructurados no cambiaron."
                st.session_state[SessionKeys.PROCESS_MESSAGE] = reused_message or (
                    f"{EXTRACTION_SUCCESS_MESSAGE}\n\n{JOB_ANALYSIS_SUCCESS_MESSAGE}\n\n"
                    f"{LINKEDIN_PROFILE_SUCCESS_MESSAGE}"
                )
                if compatibility_result.success:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = reused_message or (
                        f"{EXTRACTION_SUCCESS_MESSAGE}\n\n{JOB_ANALYSIS_SUCCESS_MESSAGE}\n\n"
                        f"{COMPATIBILITY_SUCCESS_MESSAGE}\n\n{LINKEDIN_PROFILE_SUCCESS_MESSAGE}\n\n"
                        f"{FINAL_AUDIT_SUCCESS_MESSAGE}"
                    )
                    status.update(label="Perfil, mercado, compatibilidad, LinkedIn y auditoría generados.", state="complete")
                else:
                    st.session_state[SessionKeys.PROCESS_ERROR] = (
                        compatibility_result.user_message or "No fue posible calcular la compatibilidad."
                    )
                    status.update(label="LinkedIn generado; compatibilidad pendiente.", state="error")
                return

            st.session_state[SessionKeys.PROCESS_MESSAGE] = EXTRACTION_SUCCESS_MESSAGE
            clear_compatibility_state()
            clear_linkedin_profile_generation_state()
            clear_final_audit_state()
            st.session_state[SessionKeys.PROCESS_ERROR] = _job_analysis_failure_message(job_result)
            status.update(label="No fue posible analizar las vacantes.", state="error")
            return

        clear_job_analysis_state()
        clear_compatibility_state()
        clear_linkedin_profile_generation_state()
        clear_final_audit_state()
        st.session_state[SessionKeys.PROCESS_ERROR] = (
            extraction_result.user_message
            or "No fue posible extraer el perfil profesional estructurado."
        )
        status.update(label="No fue posible extraer el perfil profesional.", state="error")


def capture_form_state() -> dict:
    """Capture the current Streamlit form state without reading file contents."""
    uploaded_file = st.session_state.get(get_cv_file_uploader_key())
    cv_file_bytes = uploaded_file.getvalue() if uploaded_file is not None else None
    jobs = []
    for index in range(int(st.session_state[SessionKeys.JOB_COUNT])):
        jobs.append(
            JobFormInput(
                index=index + 1,
                title=st.session_state[get_job_field_key(index, "title")],
                company=st.session_state[get_job_field_key(index, "company")],
                description=st.session_state[get_job_field_key(index, "description")],
                url=st.session_state[get_job_field_key(index, "url")],
            )
        )

    return {
        "consent_accepted": bool(st.session_state[SessionKeys.CONSENT_ACCEPTED]),
        "cv_text": st.session_state[SessionKeys.CV_TEXT],
        "cv_file_name": getattr(uploaded_file, "name", None),
        "cv_file_size": getattr(uploaded_file, "size", None),
        "cv_file_bytes": cv_file_bytes,
        "linkedin_text": st.session_state[SessionKeys.LINKEDIN_TEXT],
        "linkedin_url": st.session_state[SessionKeys.LINKEDIN_URL],
        "jobs": jobs,
        "output_language": st.session_state.get(SessionKeys.OUTPUT_LANGUAGE, DEFAULT_OUTPUT_LANGUAGE),
    }


def render_form_feedback() -> None:
    """Render validation messages, success text and the validated input summary."""
    messages = st.session_state[SessionKeys.VALIDATION_MESSAGES]
    if messages:
        render_validation_messages(messages)

    if st.session_state[SessionKeys.PROCESS_MESSAGE]:
        st.success(st.session_state[SessionKeys.PROCESS_MESSAGE])

    if st.session_state[SessionKeys.PROCESS_ERROR]:
        st.error(st.session_state[SessionKeys.PROCESS_ERROR])

    if st.session_state[SessionKeys.CV_PARSE_SUMMARY]:
        render_cv_diagnostic(
            st.session_state[SessionKeys.CV_PARSE_SUMMARY],
            st.session_state[SessionKeys.CV_PREVIEW],
        )

    if (
        st.session_state[SessionKeys.LINKEDIN_LINK_SUMMARY]
        or st.session_state[SessionKeys.JOB_LINK_SUMMARIES]
    ):
        render_link_diagnostics(
            st.session_state[SessionKeys.LINKEDIN_LINK_SUMMARY],
            st.session_state[SessionKeys.JOB_LINK_SUMMARIES],
            st.session_state[SessionKeys.LINK_PREVIEWS],
        )

    if st.session_state[SessionKeys.INPUT_SUMMARY]:
        render_input_summary(st.session_state[SessionKeys.INPUT_SUMMARY])


def _sync_current_cv_file(uploaded_file: object | None) -> None:
    file_name = getattr(uploaded_file, "name", None)
    file_size = getattr(uploaded_file, "size", None)
    sync_cv_file_metadata(file_name, file_size)


def _validation_state(form_state: dict) -> dict:
    return {
        "consent_accepted": form_state["consent_accepted"],
        "cv_text": form_state["cv_text"],
        "cv_file_name": form_state["cv_file_name"],
        "cv_file_size": form_state["cv_file_size"],
        "linkedin_text": form_state["linkedin_text"],
        "linkedin_url": form_state["linkedin_url"],
        "jobs": form_state["jobs"],
        "output_language": form_state["output_language"],
    }


def _preparation_state(form_state: dict) -> dict:
    return {
        "cv_text": form_state["cv_text"],
        "cv_file_name": form_state["cv_file_name"],
        "cv_file_size": form_state["cv_file_size"],
        "cv_file_bytes": form_state["cv_file_bytes"],
        "linkedin_text": form_state["linkedin_text"],
        "linkedin_url": form_state["linkedin_url"],
        "jobs": form_state["jobs"],
        "output_language": form_state["output_language"],
    }


def _dedupe_messages(messages: list[ValidationMessage]) -> list[ValidationMessage]:
    seen = set()
    deduped = []
    for message in messages:
        key = (message.level, message.field, message.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(message)
    return deduped


def _job_analysis_failure_message(result: JobAnalysisResult) -> str:
    lines = [
        result.user_message or "No fue posible analizar las vacantes objetivo.",
        "",
        "Las vacantes sí fueron recibidas si aparecen en el resumen de entrada. "
        "Este fallo ocurrió después, durante la etapa de análisis estructurado.",
    ]
    if result.error_category:
        lines.append(f"Categoría técnica: {result.error_category}.")
    if result.retryable:
        lines.append("Puedes intentar nuevamente; el fallo parece temporal.")
    if result.audit_findings:
        errors = [finding for finding in result.audit_findings if finding.startswith("error:")]
        warnings = [finding for finding in result.audit_findings if finding.startswith("warning:")]
        if errors:
            lines.append("Errores principales:")
            lines.extend(f"- {finding}" for finding in errors[:3])
        if warnings:
            lines.append("Advertencias principales:")
            lines.extend(f"- {finding}" for finding in warnings[:3])
    elif result.warnings:
        lines.append("Advertencias:")
        lines.extend(f"- {warning}" for warning in result.warnings[:3])
    return "\n".join(lines)


def _status_label_for_form_state(form_state: dict) -> str:
    if form_state["cv_text"].strip():
        return "Preparando el contenido normalizado..."

    filename = (form_state["cv_file_name"] or "").lower()
    if filename.endswith(".docx"):
        return "Leyendo el archivo DOCX..."
    if filename.endswith(".pdf"):
        return "Extrayendo texto del PDF..."
    return "Preparando el contenido normalizado..."
