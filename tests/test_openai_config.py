from __future__ import annotations

import pytest

from services.openai_config import (
    OpenAIConfigurationError,
    get_openai_configuration_status,
    load_openai_settings,
)

OPENAI_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL_FAST",
    "OPENAI_MODEL_QUALITY",
    "OPENAI_TIMEOUT_SECONDS",
    "OPENAI_MAX_RETRIES",
    "OPENAI_DIAGNOSTIC_ENABLED",
)


@pytest.fixture(autouse=True)
def clean_openai_env(monkeypatch):
    for name in OPENAI_ENV:
        monkeypatch.delenv(name, raising=False)


def _set_valid_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret")
    monkeypatch.setenv("OPENAI_MODEL_FAST", "fast-model")
    monkeypatch.setenv("OPENAI_MODEL_QUALITY", "quality-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "1")
    monkeypatch.setenv("OPENAI_DIAGNOSTIC_ENABLED", "true")


def test_load_openai_settings_valid(monkeypatch):
    _set_valid_env(monkeypatch)

    settings = load_openai_settings(load_dotenv_file=False)

    assert settings.api_key.get_secret_value() == "unit-test-secret"
    assert settings.model_fast == "fast-model"
    assert settings.model_quality == "quality-model"
    assert settings.timeout_seconds == 30
    assert settings.max_retries == 1
    assert settings.diagnostic_enabled is True


def test_missing_api_key_fails(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY")

    with pytest.raises(OpenAIConfigurationError) as exc:
        load_openai_settings(load_dotenv_file=False)

    assert "OPENAI_API_KEY" in exc.value.errors[0]


def test_missing_fast_model_fails(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.delenv("OPENAI_MODEL_FAST")

    with pytest.raises(OpenAIConfigurationError) as exc:
        load_openai_settings(load_dotenv_file=False)

    assert any("OPENAI_MODEL_FAST" in error for error in exc.value.errors)


def test_missing_quality_model_fails(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.delenv("OPENAI_MODEL_QUALITY")

    with pytest.raises(OpenAIConfigurationError) as exc:
        load_openai_settings(load_dotenv_file=False)

    assert any("OPENAI_MODEL_QUALITY" in error for error in exc.value.errors)


def test_invalid_timeout_fails(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "-1")

    with pytest.raises(OpenAIConfigurationError) as exc:
        load_openai_settings(load_dotenv_file=False)

    assert any("timeout_seconds" in error for error in exc.value.errors)


def test_negative_retries_fail(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "-1")

    with pytest.raises(OpenAIConfigurationError) as exc:
        load_openai_settings(load_dotenv_file=False)

    assert any("max_retries" in error for error in exc.value.errors)


def test_more_than_three_retries_fail(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "4")

    with pytest.raises(OpenAIConfigurationError) as exc:
        load_openai_settings(load_dotenv_file=False)

    assert any("max_retries" in error for error in exc.value.errors)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("false", False), ("1", True), ("0", False), ("sí", True), ("no", False)],
)
def test_diagnostic_boolean(monkeypatch, value, expected):
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("OPENAI_DIAGNOSTIC_ENABLED", value)

    settings = load_openai_settings(load_dotenv_file=False)

    assert settings.diagnostic_enabled is expected


def test_secret_does_not_appear_in_repr(monkeypatch):
    _set_valid_env(monkeypatch)

    settings = load_openai_settings(load_dotenv_file=False)

    assert "unit-test-secret" not in repr(settings)


def test_status_does_not_expose_key(monkeypatch):
    _set_valid_env(monkeypatch)

    status = get_openai_configuration_status(load_dotenv_file=False)
    payload = status.model_dump()

    assert status.configured
    assert payload["api_key_present"] is True
    assert "unit-test-secret" not in str(payload)


def test_status_reports_out_of_range_values(monkeypatch):
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "9")

    status = get_openai_configuration_status(load_dotenv_file=False)

    assert not status.configured
    assert any("max_retries" in error for error in status.errors)
