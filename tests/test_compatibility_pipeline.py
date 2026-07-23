from __future__ import annotations

from services.compatibility_pipeline import run_compatibility_pipeline
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings


def _factory_for(evaluation):
    return lambda: OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(evaluation)), prompt_loader=_prompt_loader)


def _prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema seguro.",
        "compatibility_analysis.txt": "Evalúa compatibilidad sin score.",
    }
    return prompts[filename]


def test_pipeline_reuses_successful_result_when_fingerprint_matches():
    profile, market, evaluation = build_compatibility_inputs()
    first = run_compatibility_pipeline(profile, market, "es", openai_service_factory=_factory_for(evaluation))

    second = run_compatibility_pipeline(
        profile,
        market,
        "es",
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        openai_service_factory=_factory_for(evaluation),
    )

    assert first.result.success is True
    assert second.reused is True
    assert second.result.reused_from_session is True
    assert "Se reutilizó" in " ".join(second.result.warnings)


def test_pipeline_force_ignores_matching_fingerprint():
    profile, market, evaluation = build_compatibility_inputs()
    first = run_compatibility_pipeline(profile, market, "es", openai_service_factory=_factory_for(evaluation))

    second = run_compatibility_pipeline(
        profile,
        market,
        "es",
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        force=True,
        openai_service_factory=_factory_for(evaluation),
    )

    assert second.reused is False
    assert second.result.success is True


def test_pipeline_configuration_error_is_safe():
    profile, market, _ = build_compatibility_inputs()

    def broken_factory():
        raise OpenAIConfigurationError(errors=["OPENAI_API_KEY no está configurada."])

    run = run_compatibility_pipeline(profile, market, "es", openai_service_factory=broken_factory)

    assert run.result.success is False
    assert run.result.error_category == "configuration_error"
    assert "OpenAI" in run.result.user_message
