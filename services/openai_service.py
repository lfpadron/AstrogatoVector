"""Encapsulated OpenAI Responses API integration."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from schemas.diagnostic_models import OpenAIDiagnosticResponse, OpenAIDiagnosticResult
from services.openai_config import OpenAISettings, load_openai_settings
from services.prompt_loader import PromptLoadError, load_prompt

T = TypeVar("T", bound=BaseModel)
PromptLoader = Callable[[str], str]

STRUCTURED_OUTPUT_ERROR_MESSAGE = (
    "El modelo respondió, pero no fue posible validar la respuesta estructurada. "
    "Revisa el modelo configurado o intenta nuevamente."
)
VALIDATION_DETAIL_PREFIX = "Detalle de validación estructurada"
MAX_VALIDATION_DETAILS = 6


class AstrogatoOpenAIError(Exception):
    """Safe internal OpenAI error representation."""

    def __init__(self, user_message: str, category: str, retryable: bool = False) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True)
class StructuredCallResult(Generic[T]):
    """Safe metadata and parsed output from a structured OpenAI call."""

    success: bool
    parsed: T | None = None
    request_id: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    warnings: list[str] = field(default_factory=list)


class OpenAIService:
    """Small wrapper around the official OpenAI client."""

    def __init__(
        self,
        settings: OpenAISettings,
        client: OpenAI | None = None,
        prompt_loader: PromptLoader = load_prompt,
    ) -> None:
        self.settings = settings
        self._client = client or OpenAI(
            api_key=settings.api_key.get_secret_value(),
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
        self._prompt_loader = prompt_loader

    def parse_structured_response(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> StructuredCallResult[T]:
        """Call Responses API and return a Pydantic parsed result plus safe metadata."""
        argument_error = _validate_call_arguments(model_name, system_prompt, user_prompt, response_model)
        if argument_error is not None:
            return StructuredCallResult(
                success=False,
                model=model_name or None,
                error_code="invalid_local_arguments",
                error_message=argument_error,
                retryable=False,
            )

        try:
            response = self._client.responses.parse(
                model=model_name,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=response_model,
            )
            request_id = _extract_request_id(response)
            usage = _extract_usage(response)
            response_model_name = _extract_response_model(response) or model_name
            parsed = getattr(response, "output_parsed", None)

            if parsed is None:
                return StructuredCallResult(
                    success=False,
                    request_id=request_id,
                    model=response_model_name,
                    **usage,
                    error_code="structured_output_unparsed",
                    error_message=STRUCTURED_OUTPUT_ERROR_MESSAGE,
                    retryable=False,
                    warnings=[
                        f"{VALIDATION_DETAIL_PREFIX}: response.output_parsed llegó vacío.",
                    ],
                )

            if not isinstance(parsed, response_model):
                return StructuredCallResult(
                    success=False,
                    request_id=request_id,
                    model=response_model_name,
                    **usage,
                    error_code="structured_output_type_mismatch",
                    error_message=STRUCTURED_OUTPUT_ERROR_MESSAGE,
                    retryable=False,
                    warnings=[
                        f"{VALIDATION_DETAIL_PREFIX}: se recibió {type(parsed).__name__}; "
                        f"se esperaba {response_model.__name__}.",
                    ],
                )

            return StructuredCallResult(
                success=True,
                parsed=parsed,
                request_id=request_id,
                model=response_model_name,
                **usage,
            )
        except ValidationError as exc:
            return StructuredCallResult(
                success=False,
                model=model_name,
                error_code="pydantic_validation_error",
                error_message=STRUCTURED_OUTPUT_ERROR_MESSAGE,
                retryable=False,
                warnings=_format_validation_error_warnings(exc),
            )
        except Exception as exc:  # noqa: BLE001 - all SDK errors must be mapped safely.
            error = _map_openai_exception(exc)
            return StructuredCallResult(
                success=False,
                model=model_name,
                error_code=error.category,
                error_message=error.user_message,
                retryable=error.retryable,
            )

    def run_diagnostic(self) -> OpenAIDiagnosticResult:
        """Run the small OpenAI structured diagnostic without user form data."""
        if not self.settings.diagnostic_enabled:
            return OpenAIDiagnosticResult(
                success=False,
                model_used=self.settings.model_fast,
                error_category="diagnostic_disabled",
                user_message="El diagnóstico de OpenAI está deshabilitado por configuración.",
                retryable=False,
            )

        start_time = time.perf_counter()
        try:
            system_prompt = self._prompt_loader("diagnostic_system.txt")
            user_prompt = self._prompt_loader("diagnostic_user.txt")
        except PromptLoadError:
            return OpenAIDiagnosticResult(
                success=False,
                model_used=self.settings.model_fast,
                latency_ms=_elapsed_ms(start_time),
                error_category="prompt_load_error",
                user_message="No fue posible cargar los prompts de diagnóstico.",
                retryable=False,
            )

        result = self.parse_structured_response(
            model_name=self.settings.model_fast,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=OpenAIDiagnosticResponse,
        )
        latency_ms = _elapsed_ms(start_time)

        if not result.success or result.parsed is None:
            return OpenAIDiagnosticResult(
                success=False,
                model_used=result.model or self.settings.model_fast,
                request_id=result.request_id,
                latency_ms=latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                error_category=result.error_code,
                user_message=result.error_message or "Ocurrió un error inesperado al comunicarse con OpenAI.",
                retryable=result.retryable,
            )

        return OpenAIDiagnosticResult(
            success=True,
            response=result.parsed,
            model_used=result.model or self.settings.model_fast,
            request_id=result.request_id,
            latency_ms=latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
        )


def create_openai_service() -> OpenAIService:
    """Create an OpenAI service from environment configuration."""
    return OpenAIService(load_openai_settings())


def generate_with_openai(prompt: str) -> str:
    """Compatibility placeholder for future professional generation."""
    _ = prompt
    raise NotImplementedError("Se implementará en un incremento posterior.")


def _validate_call_arguments(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
) -> str | None:
    if not model_name.strip():
        return "El modelo de OpenAI no está configurado."
    if not system_prompt.strip() or not user_prompt.strip():
        return "Los prompts de OpenAI no pueden estar vacíos."
    if not isinstance(response_model, type) or not issubclass(response_model, BaseModel):
        return "El modelo de respuesta debe ser un modelo Pydantic."
    return None


def _extract_request_id(response: object) -> str | None:
    value = getattr(response, "_request_id", None)
    return str(value) if value else None


def _extract_response_model(response: object) -> str | None:
    value = getattr(response, "model", None)
    return str(value) if value else None


def _extract_usage(response: object) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": _usage_value(usage, "input_tokens"),
        "output_tokens": _usage_value(usage, "output_tokens"),
        "total_tokens": _usage_value(usage, "total_tokens"),
    }


def _usage_value(usage: object, name: str) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _format_validation_error_warnings(exc: ValidationError) -> list[str]:
    warnings: list[str] = []
    errors = exc.errors(include_input=False, include_url=False)
    for error in errors[:MAX_VALIDATION_DETAILS]:
        location = _format_validation_location(error.get("loc"))
        message = str(error.get("msg") or "Regla incumplida.")
        error_type = str(error.get("type") or "validation_error")
        warnings.append(f"{VALIDATION_DETAIL_PREFIX}: {location}: {message} ({error_type}).")
    omitted_count = len(errors) - MAX_VALIDATION_DETAILS
    if omitted_count > 0:
        warnings.append(
            f"{VALIDATION_DETAIL_PREFIX}: {omitted_count} error(es) adicional(es) omitido(s) para mantener "
            "la salida breve."
        )
    return warnings


def _format_validation_location(location: object) -> str:
    if not isinstance(location, (list, tuple)) or not location:
        return "respuesta"

    parts: list[str] = []
    for item in location:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
            continue
        parts.append(str(item))
    return ".".join(parts) if parts else "respuesta"


def _map_openai_exception(exc: Exception) -> AstrogatoOpenAIError:
    if isinstance(exc, AuthenticationError):
        return AstrogatoOpenAIError(
            "No fue posible autenticar la conexión con OpenAI. Revisa la API key configurada.",
            "authentication_error",
            retryable=False,
        )
    if isinstance(exc, PermissionDeniedError):
        return AstrogatoOpenAIError(
            "La cuenta configurada no tiene permisos para utilizar el modelo seleccionado.",
            "permission_error",
            retryable=False,
        )
    if isinstance(exc, NotFoundError):
        return AstrogatoOpenAIError(
            "El modelo configurado no existe o no está disponible para esta cuenta. "
            "Revisa OPENAI_MODEL_FAST y OPENAI_MODEL_QUALITY.",
            "model_not_found",
            retryable=False,
        )
    if isinstance(exc, RateLimitError):
        return AstrogatoOpenAIError(
            "OpenAI limitó temporalmente la solicitud. Intenta nuevamente más tarde.",
            "rate_limit_error",
            retryable=True,
        )
    if isinstance(exc, APITimeoutError):
        return AstrogatoOpenAIError(
            "La solicitud tardó más de lo permitido. Intenta nuevamente.",
            "timeout_error",
            retryable=True,
        )
    if isinstance(exc, APIConnectionError):
        return AstrogatoOpenAIError(
            "No fue posible establecer comunicación con OpenAI. Revisa la conexión a internet.",
            "connection_error",
            retryable=True,
        )
    if isinstance(exc, BadRequestError):
        return AstrogatoOpenAIError(
            "OpenAI rechazó la solicitud. Revisa la configuración del modelo y el esquema de respuesta.",
            "invalid_request_error",
            retryable=False,
        )
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        if status_code in {408, 409, 429} or (status_code is not None and status_code >= 500):
            return AstrogatoOpenAIError(
                "OpenAI presentó un error temporal. Intenta nuevamente.",
                "server_error",
                retryable=True,
            )
        return AstrogatoOpenAIError(
            "OpenAI rechazó la solicitud. Revisa la configuración del modelo y el esquema de respuesta.",
            "api_status_error",
            retryable=False,
        )
    return AstrogatoOpenAIError(
        "Ocurrió un error inesperado al comunicarse con OpenAI.",
        "unexpected_error",
        retryable=False,
    )


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))
