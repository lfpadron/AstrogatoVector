"""Typed OpenAI configuration loading for Astrogato Vector."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import Field, SecretStr, ValidationError

from schemas.base import StrictBaseModel

CONFIGURATION_ERROR_MESSAGE = (
    "La configuración de OpenAI está incompleta. Revisa el archivo .env y confirma que "
    "OPENAI_API_KEY y los modelos estén definidos."
)


class OpenAIConfigurationError(Exception):
    """Raised when local OpenAI configuration is missing or invalid."""

    def __init__(self, message: str = CONFIGURATION_ERROR_MESSAGE, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.user_message = message
        self.errors = errors or []


class OpenAISettings(StrictBaseModel):
    """Validated OpenAI settings read from environment variables."""

    api_key: SecretStr = Field(description="OpenAI API key, never displayed.")
    model_fast: str = Field(min_length=1)
    model_quality: str = Field(min_length=1)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    max_retries: int = Field(default=1, ge=0, le=3)
    diagnostic_enabled: bool = True


class OpenAIConfigurationStatus(StrictBaseModel):
    """Safe OpenAI configuration status for UI display."""

    configured: bool
    api_key_present: bool
    model_fast_present: bool
    model_quality_present: bool
    diagnostic_enabled: bool
    model_fast: str | None = None
    model_quality: str | None = None
    timeout_seconds: float | None = None
    max_retries: int | None = None
    errors: list[str] = Field(default_factory=list)


def load_openai_settings(*, load_dotenv_file: bool = True) -> OpenAISettings:
    """Load and validate OpenAI settings without exposing secrets."""
    if load_dotenv_file:
        load_dotenv(override=False)

    errors: list[str] = []
    api_key = _read_env("OPENAI_API_KEY")
    model_fast = _read_env("OPENAI_MODEL_FAST")
    model_quality = _read_env("OPENAI_MODEL_QUALITY")

    if not api_key:
        errors.append("OPENAI_API_KEY no está definida.")
    if not model_fast:
        errors.append("OPENAI_MODEL_FAST no está definido.")
    if not model_quality:
        errors.append("OPENAI_MODEL_QUALITY no está definido.")

    timeout_seconds = _read_float_env("OPENAI_TIMEOUT_SECONDS", 60, errors)
    max_retries = _read_int_env("OPENAI_MAX_RETRIES", 1, errors)
    diagnostic_enabled = _read_bool_env("OPENAI_DIAGNOSTIC_ENABLED", True, errors)

    if errors:
        raise OpenAIConfigurationError(errors=errors)

    try:
        return OpenAISettings(
            api_key=SecretStr(api_key or ""),
            model_fast=model_fast or "",
            model_quality=model_quality or "",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            diagnostic_enabled=diagnostic_enabled,
        )
    except ValidationError as exc:
        safe_errors = _safe_validation_errors(exc)
        raise OpenAIConfigurationError(errors=safe_errors) from exc


def get_openai_configuration_status(*, load_dotenv_file: bool = True) -> OpenAIConfigurationStatus:
    """Return safe configuration status without creating an OpenAI client."""
    if load_dotenv_file:
        load_dotenv(override=False)

    errors: list[str] = []
    api_key_present = bool(_read_env("OPENAI_API_KEY"))
    model_fast = _read_env("OPENAI_MODEL_FAST")
    model_quality = _read_env("OPENAI_MODEL_QUALITY")
    timeout_seconds = _read_float_env("OPENAI_TIMEOUT_SECONDS", 60, errors)
    max_retries = _read_int_env("OPENAI_MAX_RETRIES", 1, errors)
    diagnostic_enabled = _read_bool_env("OPENAI_DIAGNOSTIC_ENABLED", True, errors)

    if not api_key_present:
        errors.append("OPENAI_API_KEY no está definida.")
    if not model_fast:
        errors.append("OPENAI_MODEL_FAST no está definido.")
    if not model_quality:
        errors.append("OPENAI_MODEL_QUALITY no está definido.")
    if not errors:
        try:
            OpenAISettings(
                api_key=SecretStr("configured"),
                model_fast=model_fast or "",
                model_quality=model_quality or "",
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                diagnostic_enabled=diagnostic_enabled,
            )
        except ValidationError as exc:
            errors.extend(_safe_validation_errors(exc))

    return OpenAIConfigurationStatus(
        configured=not errors,
        api_key_present=api_key_present,
        model_fast_present=bool(model_fast),
        model_quality_present=bool(model_quality),
        diagnostic_enabled=diagnostic_enabled,
        model_fast=model_fast,
        model_quality=model_quality,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        errors=errors,
    )


def _read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _read_float_env(name: str, default: float, errors: list[str]) -> float:
    value = _read_env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        errors.append(f"{name} debe ser un número.")
        return default


def _read_int_env(name: str, default: int, errors: list[str]) -> int:
    value = _read_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        errors.append(f"{name} debe ser un entero.")
        return default


def _read_bool_env(name: str, default: bool, errors: list[str]) -> bool:
    value = _read_env(name)
    if value is None:
        return default

    normalized = value.casefold()
    if normalized in {"1", "true", "yes", "y", "on", "si", "sí"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    errors.append(f"{name} debe ser true o false.")
    return default


def _safe_validation_errors(exc: ValidationError) -> list[str]:
    messages = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "configuración"
        messages.append(f"{location}: {error.get('msg', 'valor inválido')}")
    return messages
