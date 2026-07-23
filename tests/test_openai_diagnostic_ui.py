from __future__ import annotations

from streamlit.testing.v1 import AppTest

import services.openai_service as openai_service_module
from schemas.diagnostic_models import DiagnosticCapability, OpenAIDiagnosticResponse, OpenAIDiagnosticResult
from schemas.extraction_models import CandidateExtractionResult
from services.openai_config import OpenAIConfigurationStatus
from services.candidate_extraction_pipeline import CandidateExtractionRun
from utils.session import SessionKeys


class FakeService:
    def __init__(self, result: OpenAIDiagnosticResult) -> None:
        self.result = result
        self.calls = 0

    def run_diagnostic(self) -> OpenAIDiagnosticResult:
        self.calls += 1
        return self.result


def test_openai_diagnostic_ui_shows_incomplete_configuration_without_secret():
    status = OpenAIConfigurationStatus(
        configured=False,
        api_key_present=False,
        model_fast_present=False,
        model_quality_present=False,
        diagnostic_enabled=True,
        errors=["OPENAI_API_KEY no está definida."],
    )

    at = AppTest.from_function(_render_component, kwargs={"status": status, "service": FakeService(_success_result())})
    at.run()

    page_text = _page_text(at)
    assert "Configuración de OpenAI incompleta" in page_text
    assert "API key configurada" in page_text
    assert "unit-test-secret" not in page_text


def test_openai_diagnostic_ui_hides_button_when_disabled():
    status = OpenAIConfigurationStatus(
        configured=True,
        api_key_present=True,
        model_fast_present=True,
        model_quality_present=True,
        diagnostic_enabled=False,
        model_fast="fast-model",
        model_quality="quality-model",
        timeout_seconds=60,
        max_retries=1,
    )

    at = AppTest.from_function(_render_component, kwargs={"status": status, "service": FakeService(_success_result())})
    at.run()

    assert "Probar conexión con OpenAI" not in [button.label for button in at.button]
    assert "deshabilitado" in _page_text(at)


def test_openai_diagnostic_ui_success_with_mock_service():
    service = FakeService(_success_result())
    at = AppTest.from_function(
        _render_component,
        kwargs={"status": _configured_status(), "service": service},
    )
    at.run()
    at.button[0].click()
    at.run()

    page_text = _page_text(at)
    assert service.calls == 1
    assert "Conexión con OpenAI verificada correctamente" in page_text
    assert "fast-model" in page_text
    assert "unit-test-secret" not in page_text


def test_openai_diagnostic_ui_failure_with_mock_service():
    service = FakeService(
        OpenAIDiagnosticResult(
            success=False,
            model_used="fast-model",
            error_category="authentication_error",
            user_message="No fue posible autenticar la conexión con OpenAI. Revisa la API key configurada.",
            retryable=False,
        )
    )
    at = AppTest.from_function(
        _render_component,
        kwargs={"status": _configured_status(), "service": service},
    )
    at.run()
    at.button[0].click()
    at.run()

    page_text = _page_text(at)
    assert service.calls == 1
    assert "No fue posible autenticar" in page_text
    assert "authentication_error" in page_text
    assert "unit-test-secret" not in page_text


def test_process_button_does_not_call_openai(monkeypatch):
    _clear_openai_env(monkeypatch)

    def fail_openai(**kwargs):
        raise AssertionError("Procesar must not create an OpenAI client")

    def fake_candidate_pipeline(*args, **kwargs):
        return CandidateExtractionRun(
            result=CandidateExtractionResult(
                success=False,
                error_category="configuration_error",
                user_message="La configuración de OpenAI está incompleta.",
                retryable=False,
            ),
            fingerprint=None,
            reused=False,
        )

    monkeypatch.setattr(openai_service_module, "OpenAI", fail_openai)
    monkeypatch.setattr("components.candidate_extraction_flow.run_candidate_extraction_pipeline", fake_candidate_pipeline)
    long_cv = (
        "Experiencia profesional en producto, estrategia, datos, liderazgo, comunicación ejecutiva "
        "y coordinación de equipos en organizaciones tecnológicas. "
        * 3
    )
    long_job = (
        "Responsable de liderar iniciativas estratégicas, coordinar equipos multifuncionales, "
        "analizar métricas de negocio y comunicar prioridades con stakeholders internos. "
        * 2
    )
    at = AppTest.from_file("app.py").run(timeout=10)
    diagnostic_payload = {
        "success": False,
        "response": None,
        "model_used": "fast-model",
        "request_id": None,
        "latency_ms": 1,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "error_category": "timeout_error",
        "user_message": "La solicitud tardó más de lo permitido. Intenta nuevamente.",
        "retryable": True,
    }
    at.session_state[SessionKeys.OPENAI_DIAGNOSTIC_RESULT] = diagnostic_payload
    at.checkbox[0].check()
    at.text_area[0].set_value(long_cv)
    at.text_input[1].set_value("Product Manager")
    at.text_area[2].set_value(long_job)
    at.text_input[4].set_value("Program Manager")
    at.text_area[3].set_value(long_job)
    next(button for button in at.button if button.label == "Procesar").click()
    at.run(timeout=10)

    assert len(at.exception) == 0
    assert at.session_state["validated_input"] is not None
    assert at.session_state[SessionKeys.OPENAI_DIAGNOSTIC_RESULT] == diagnostic_payload
    assert "configuración de OpenAI está incompleta" in at.session_state["process_error"]


def _clear_openai_env(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL_FAST",
        "OPENAI_MODEL_QUALITY",
        "OPENAI_TIMEOUT_SECONDS",
        "OPENAI_MAX_RETRIES",
        "OPENAI_DIAGNOSTIC_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)


def _render_component(status, service):
    from components.openai_diagnostic import render_openai_diagnostic_sidebar
    from utils.session import initialize_session_state

    initialize_session_state()
    render_openai_diagnostic_sidebar(
        status_provider=lambda: status,
        service_factory=lambda: service,
    )


def _configured_status() -> OpenAIConfigurationStatus:
    return OpenAIConfigurationStatus(
        configured=True,
        api_key_present=True,
        model_fast_present=True,
        model_quality_present=True,
        diagnostic_enabled=True,
        model_fast="fast-model",
        model_quality="quality-model",
        timeout_seconds=60,
        max_retries=1,
    )


def _success_result() -> OpenAIDiagnosticResult:
    return OpenAIDiagnosticResult(
        success=True,
        model_used="fast-model",
        request_id="req_test",
        latency_ms=123,
        input_tokens=4,
        output_tokens=9,
        total_tokens=13,
        response=OpenAIDiagnosticResponse(
            operational=True,
            detected_language="es",
            confirmation_message="El diagnóstico estructurado está operativo.",
            capabilities=[
                DiagnosticCapability(name="Extracción", description="Extraer evidencia profesional."),
                DiagnosticCapability(name="Perfil", description="Generar texto de perfil revisable."),
                DiagnosticCapability(name="Compatibilidad", description="Estimar alineación futura."),
            ],
            human_review_warning="Todo contenido generado con IA requiere revisión humana antes de usarse.",
        ),
    )


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    return "\n".join(values)
