from __future__ import annotations

from pydantic import SecretStr

from schemas.diagnostic_models import DiagnosticCapability, OpenAIDiagnosticResponse
from services.openai_config import OpenAISettings
from services.openai_service import OpenAIService


class FakeSDKResponse:
    def __init__(self, output_parsed=None, model: str = "fast-model") -> None:
        self.output_parsed = output_parsed
        self._request_id = "req_diag"
        self.model = model
        self.usage = {"input_tokens": 3, "output_tokens": 8, "total_tokens": 11}


class FakeResponses:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeClient:
    def __init__(self, result) -> None:
        self.responses = FakeResponses(result)


def test_run_diagnostic_success():
    parsed = _diagnostic_response()
    client = FakeClient(FakeSDKResponse(parsed))
    service = OpenAIService(_settings(), client=client, prompt_loader=_prompt_loader)

    result = service.run_diagnostic()

    assert result.success
    assert result.response is not None
    assert len(result.response.capabilities) == 3
    assert result.response.detected_language == "es"
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert result.model_used == "fast-model"
    assert result.input_tokens == 3


def test_run_diagnostic_uses_fast_model_not_quality_model():
    client = FakeClient(FakeSDKResponse(_diagnostic_response()))
    service = OpenAIService(_settings(), client=client, prompt_loader=_prompt_loader)

    service.run_diagnostic()

    assert client.responses.calls[0]["model"] == "fast-model"
    assert client.responses.calls[0]["model"] != "quality-model"


def test_run_diagnostic_does_not_use_form_content():
    client = FakeClient(FakeSDKResponse(_diagnostic_response()))
    service = OpenAIService(_settings(), client=client, prompt_loader=_prompt_loader)

    service.run_diagnostic()

    payload = str(client.responses.calls[0]["input"])
    assert "curriculum" not in payload.casefold()
    assert "vacante" not in payload.casefold()
    assert "linkedin.com/in/" not in payload.casefold()


def test_run_diagnostic_disabled():
    service = OpenAIService(
        _settings(diagnostic_enabled=False),
        client=FakeClient(FakeSDKResponse(_diagnostic_response())),
        prompt_loader=_prompt_loader,
    )

    result = service.run_diagnostic()

    assert not result.success
    assert result.error_category == "diagnostic_disabled"


def test_run_diagnostic_failure_is_safe():
    service = OpenAIService(_settings(), client=FakeClient(FakeSDKResponse(output_parsed=None)), prompt_loader=_prompt_loader)

    result = service.run_diagnostic()

    assert not result.success
    assert result.error_category == "structured_output_unparsed"
    assert "unit-test-secret" not in (result.user_message or "")


def _settings(diagnostic_enabled: bool = True) -> OpenAISettings:
    return OpenAISettings(
        api_key=SecretStr("unit-test-secret"),
        model_fast="fast-model",
        model_quality="quality-model",
        timeout_seconds=30,
        max_retries=1,
        diagnostic_enabled=diagnostic_enabled,
    )


def _prompt_loader(filename: str) -> str:
    prompts = {
        "diagnostic_system.txt": "Sistema de diagnóstico sin datos de usuario.",
        "diagnostic_user.txt": "Realiza una prueba breve de diagnóstico.",
    }
    return prompts[filename]


def _diagnostic_response() -> OpenAIDiagnosticResponse:
    return OpenAIDiagnosticResponse(
        operational=True,
        detected_language="es",
        confirmation_message="El diagnóstico estructurado está operativo.",
        capabilities=[
            DiagnosticCapability(name="Extracción", description="Extraer evidencia profesional en el futuro."),
            DiagnosticCapability(name="Perfil", description="Generar textos de perfil con revisión humana."),
            DiagnosticCapability(name="Compatibilidad", description="Estimar alineación con vacantes objetivo."),
        ],
        human_review_warning="Todo contenido generado con IA requiere revisión humana antes de usarse.",
    )
