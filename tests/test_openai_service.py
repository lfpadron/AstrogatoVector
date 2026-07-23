from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import SecretStr, ValidationError

import services.openai_service as openai_service_module
from schemas.diagnostic_models import DiagnosticCapability, OpenAIDiagnosticResponse
from services.openai_config import OpenAISettings
from services.openai_service import OpenAIService, STRUCTURED_OUTPUT_ERROR_MESSAGE


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 20
    total_tokens: int = 30


class FakeSDKResponse:
    def __init__(
        self,
        *,
        output_parsed=None,
        request_id: str | None = "req_test",
        usage=None,
        model: str | None = "fast-model",
    ) -> None:
        self.output_parsed = output_parsed
        self._request_id = request_id
        self.usage = usage
        self.model = model


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


def test_service_constructs_client_with_timeout_retries_and_api_key(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.responses = FakeResponses(FakeSDKResponse(output_parsed=_diagnostic_response()))

    monkeypatch.setattr(openai_service_module, "OpenAI", FakeOpenAI)

    OpenAIService(_settings())

    assert captured["api_key"] == "unit-test-secret"
    assert captured["timeout"] == 30
    assert captured["max_retries"] == 1


def test_injected_client_avoids_real_client_creation(monkeypatch):
    def fail_openai(**kwargs):
        raise AssertionError("OpenAI constructor should not be called")

    monkeypatch.setattr(openai_service_module, "OpenAI", fail_openai)

    service = OpenAIService(_settings(), client=FakeClient(FakeSDKResponse(output_parsed=_diagnostic_response())))

    assert service._client.responses


def test_parse_structured_response_success():
    parsed = _diagnostic_response()
    client = FakeClient(FakeSDKResponse(output_parsed=parsed, usage=FakeUsage()))
    service = OpenAIService(_settings(), client=client)

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert result.success
    assert result.parsed == parsed
    assert result.request_id == "req_test"
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert result.total_tokens == 30
    call = client.responses.calls[0]
    assert call["model"] == "fast-model"
    assert call["text_format"] is OpenAIDiagnosticResponse
    assert "CV" not in str(call["input"])


def test_parse_structured_response_output_parsed_none():
    service = OpenAIService(_settings(), client=FakeClient(FakeSDKResponse(output_parsed=None)))

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert not result.success
    assert result.error_code == "structured_output_unparsed"
    assert result.error_message == STRUCTURED_OUTPUT_ERROR_MESSAGE


def test_parse_structured_response_unexpected_type():
    service = OpenAIService(_settings(), client=FakeClient(FakeSDKResponse(output_parsed={"ok": True})))

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert not result.success
    assert result.error_code == "structured_output_type_mismatch"


def test_parse_structured_response_pydantic_validation_error():
    try:
        OpenAIDiagnosticResponse.model_validate({})
    except ValidationError as exc:
        validation_error = exc

    service = OpenAIService(_settings(), client=FakeClient(validation_error))

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert not result.success
    assert result.error_code == "pydantic_validation_error"
    assert any("Detalle de validación estructurada" in warning for warning in result.warnings)
    assert any("operational" in warning for warning in result.warnings)


def test_parse_structured_response_usage_absent_and_model_absent():
    parsed = _diagnostic_response()
    service = OpenAIService(
        _settings(),
        client=FakeClient(FakeSDKResponse(output_parsed=parsed, request_id=None, usage=None, model=None)),
    )

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert result.success
    assert result.model == "fast-model"
    assert result.request_id is None
    assert result.total_tokens is None


def test_parse_structured_response_empty_response_object():
    service = OpenAIService(_settings(), client=FakeClient(object()))

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert not result.success
    assert result.error_code == "structured_output_unparsed"


@pytest.mark.parametrize(
    ("exception_factory", "category", "retryable"),
    [
        (lambda: _status_exception(AuthenticationError, 401, "bad unit-test-secret"), "authentication_error", False),
        (lambda: _status_exception(PermissionDeniedError, 403, "forbidden"), "permission_error", False),
        (lambda: _status_exception(NotFoundError, 404, "missing"), "model_not_found", False),
        (lambda: _status_exception(RateLimitError, 429, "limit"), "rate_limit_error", True),
        (lambda: APITimeoutError(_request()), "timeout_error", True),
        (lambda: APIConnectionError(message="network", request=_request()), "connection_error", True),
        (lambda: _status_exception(BadRequestError, 400, "bad request"), "invalid_request_error", False),
        (lambda: _status_exception(APIStatusError, 500, "server"), "server_error", True),
        (lambda: RuntimeError("surprise unit-test-secret"), "unexpected_error", False),
    ],
)
def test_openai_errors_are_mapped_safely(exception_factory, category, retryable):
    service = OpenAIService(_settings(), client=FakeClient(exception_factory()))

    result = service.parse_structured_response(
        model_name="fast-model",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert not result.success
    assert result.error_code == category
    assert result.retryable is retryable
    assert "unit-test-secret" not in (result.error_message or "")


def test_invalid_local_arguments_return_safe_error():
    service = OpenAIService(_settings(), client=FakeClient(FakeSDKResponse(output_parsed=_diagnostic_response())))

    result = service.parse_structured_response(
        model_name="",
        system_prompt="Sistema",
        user_prompt="Usuario",
        response_model=OpenAIDiagnosticResponse,
    )

    assert not result.success
    assert result.error_code == "invalid_local_arguments"


def _settings(diagnostic_enabled: bool = True) -> OpenAISettings:
    return OpenAISettings(
        api_key=SecretStr("unit-test-secret"),
        model_fast="fast-model",
        model_quality="quality-model",
        timeout_seconds=30,
        max_retries=1,
        diagnostic_enabled=diagnostic_enabled,
    )


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


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def _status_exception(cls, status_code: int, message: str):
    response = httpx.Response(status_code, request=_request())
    return cls(message, response=response, body=None)
