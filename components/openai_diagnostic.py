"""OpenAI diagnostic sidebar UI."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import streamlit as st

from schemas.diagnostic_models import OpenAIDiagnosticResult
from services.openai_config import (
    OpenAIConfigurationError,
    OpenAIConfigurationStatus,
    get_openai_configuration_status,
)
from services.openai_service import OpenAIService, create_openai_service
from utils.session import SessionKeys

StatusProvider = Callable[[], OpenAIConfigurationStatus]
ServiceFactory = Callable[[], OpenAIService]
OPENAI_DIAGNOSTIC_RESULT_KEY = getattr(SessionKeys, "OPENAI_DIAGNOSTIC_RESULT", "openai_diagnostic_result")
OPENAI_DIAGNOSTIC_LAST_RUN_KEY = getattr(SessionKeys, "OPENAI_DIAGNOSTIC_LAST_RUN", "openai_diagnostic_last_run")
OPENAI_DIAGNOSTIC_RUNNING_KEY = getattr(SessionKeys, "OPENAI_DIAGNOSTIC_RUNNING", "openai_diagnostic_running")


def render_openai_diagnostic_sidebar(
    *,
    status_provider: StatusProvider = get_openai_configuration_status,
    service_factory: ServiceFactory = create_openai_service,
) -> None:
    """Render a safe, manual OpenAI diagnostic independent from processing."""
    with st.sidebar.expander("Diagnóstico de OpenAI", expanded=False):
        status = status_provider()
        _render_configuration_status(status)

        if not status.diagnostic_enabled:
            st.info("El diagnóstico de OpenAI está deshabilitado por configuración.")
        else:
            st.session_state.setdefault(OPENAI_DIAGNOSTIC_RUNNING_KEY, False)
            button_disabled = st.session_state[OPENAI_DIAGNOSTIC_RUNNING_KEY] or not status.configured
            if st.button(
                "Probar conexión con OpenAI",
                disabled=button_disabled,
                use_container_width=True,
            ):
                _run_diagnostic(service_factory, status)

        _render_saved_result()


def _render_configuration_status(status: OpenAIConfigurationStatus) -> None:
    st.caption("Estado de configuración")
    st.markdown(f"**API key configurada:** {'Sí' if status.api_key_present else 'No'}")
    st.markdown(f"**Modelo rápido:** {status.model_fast or 'No configurado'}")
    st.markdown(f"**Modelo de calidad:** {status.model_quality or 'No configurado'}")
    st.markdown(f"**Timeout:** {status.timeout_seconds if status.timeout_seconds is not None else 'No válido'} s")
    st.markdown(f"**Reintentos:** {status.max_retries if status.max_retries is not None else 'No válido'}")

    if status.configured:
        st.success("Configuración de OpenAI completa.")
    else:
        st.warning("Configuración de OpenAI incompleta.")
        for error in status.errors:
            st.caption(error)


def _run_diagnostic(service_factory: ServiceFactory, status: OpenAIConfigurationStatus) -> None:
    st.session_state[OPENAI_DIAGNOSTIC_RUNNING_KEY] = True
    try:
        with st.spinner("Verificando conexión y respuesta estructurada..."):
            try:
                result = service_factory().run_diagnostic()
            except OpenAIConfigurationError as exc:
                result = OpenAIDiagnosticResult(
                    success=False,
                    model_used=status.model_fast,
                    error_category="configuration_error",
                    user_message=exc.user_message,
                    retryable=False,
                )
            st.session_state[OPENAI_DIAGNOSTIC_RESULT_KEY] = result.model_dump()
            st.session_state[OPENAI_DIAGNOSTIC_LAST_RUN_KEY] = datetime.now().isoformat(timespec="seconds")
    finally:
        st.session_state[OPENAI_DIAGNOSTIC_RUNNING_KEY] = False


def _render_saved_result() -> None:
    raw_result = st.session_state.get(OPENAI_DIAGNOSTIC_RESULT_KEY)
    if not raw_result:
        return

    result = OpenAIDiagnosticResult.model_validate(raw_result)
    last_run = st.session_state.get(OPENAI_DIAGNOSTIC_LAST_RUN_KEY)
    if last_run:
        st.caption(f"Última prueba: {last_run}")

    if result.success and result.response:
        st.success("Conexión con OpenAI verificada correctamente.")
        st.markdown(f"**Modelo utilizado:** {result.model_used or 'No disponible'}")
        if result.latency_ms is not None:
            st.markdown(f"**Latencia:** {result.latency_ms} ms")
        st.markdown(f"**Estado operativo:** {'Sí' if result.response.operational else 'No'}")
        st.markdown(f"**Confirmación:** {result.response.confirmation_message}")
        st.markdown("**Capacidades futuras:**")
        for capability in result.response.capabilities:
            st.caption(f"{capability.name}: {capability.description}")
        st.warning(result.response.human_review_warning)
    else:
        st.error(result.user_message or "Ocurrió un error inesperado al comunicarse con OpenAI.")
        st.caption(f"Categoría: {result.error_category or 'desconocida'}")
        st.caption(f"Reintentable: {'Sí' if result.retryable else 'No'}")
        if result.model_used:
            st.caption(f"Modelo intentado: {result.model_used}")

    with st.expander("Detalles técnicos"):
        st.caption(f"Request ID: {result.request_id or 'No disponible'}")
        st.caption(f"Tokens de entrada: {_token_label(result.input_tokens)}")
        st.caption(f"Tokens de salida: {_token_label(result.output_tokens)}")
        st.caption(f"Tokens totales: {_token_label(result.total_tokens)}")


def _token_label(value: int | None) -> str:
    return str(value) if value is not None else "No disponible"
