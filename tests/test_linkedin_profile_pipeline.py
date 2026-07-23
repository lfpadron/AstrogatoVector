from __future__ import annotations

from schemas.enums import OutputLanguage
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from services.linkedin_profile_generation_pipeline import run_linkedin_profile_generation_pipeline
from services.linkedin_profile_generation_service import build_linkedin_profile_generation_fingerprint
from services.openai_config import OpenAIConfigurationError
from services.openai_service import OpenAIService
from tests.linkedin_profile_helpers import (
    FakeClient,
    FakeSDKResponse,
    build_candidate_profile,
    build_linkedin_output,
    build_market_analysis,
    fake_settings,
)


def test_pipeline_reuses_successful_result_for_same_fingerprint():
    profile = build_candidate_profile()
    market = build_market_analysis()
    previous = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
    )
    fingerprint = build_linkedin_profile_generation_fingerprint(
        profile,
        market,
        OutputLanguage.ES,
        model_name="quality-model",
    )
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(build_linkedin_output())))

    run = run_linkedin_profile_generation_pipeline(
        profile,
        market,
        OutputLanguage.ES,
        existing_result=previous,
        existing_fingerprint=fingerprint,
        openai_service_factory=factory,
    )

    assert run.reused
    assert run.result.reused_from_session
    assert calls["count"] == 1


def test_pipeline_force_reprocess_calls_model_again():
    profile = build_candidate_profile()
    market = build_market_analysis()
    previous = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
    )
    fingerprint = build_linkedin_profile_generation_fingerprint(
        profile,
        market,
        OutputLanguage.ES,
        model_name="quality-model",
    )
    client = FakeClient(FakeSDKResponse(build_linkedin_output()))

    run = run_linkedin_profile_generation_pipeline(
        profile,
        market,
        OutputLanguage.ES,
        existing_result=previous,
        existing_fingerprint=fingerprint,
        force=True,
        openai_service_factory=lambda: OpenAIService(fake_settings(), client=client),
    )

    assert not run.reused
    assert len(client.responses.calls) == 1
    assert run.fingerprint == fingerprint


def test_pipeline_configuration_error_is_safe():
    def factory():
        raise OpenAIConfigurationError(errors=["OPENAI_API_KEY no esta definida."])

    run = run_linkedin_profile_generation_pipeline(
        build_candidate_profile(),
        build_market_analysis(),
        OutputLanguage.ES,
        openai_service_factory=factory,
    )

    assert not run.result.success
    assert run.result.error_category == "configuration_error"
    assert run.result.profile_output is None


def test_fingerprint_changes_with_candidate_market_language_model_or_prompt_version():
    profile = build_candidate_profile()
    market = build_market_analysis()
    base = build_linkedin_profile_generation_fingerprint(
        profile,
        market,
        OutputLanguage.ES,
        model_name="quality-model",
    )
    changed_profile = profile.model_copy(update={"summary": profile.summary + " Cambio."})
    changed_market = market.model_copy(update={"market_summary": market.market_summary + " Cambio."})

    assert base != build_linkedin_profile_generation_fingerprint(
        changed_profile,
        market,
        OutputLanguage.ES,
        model_name="quality-model",
    )
    assert base != build_linkedin_profile_generation_fingerprint(
        profile,
        changed_market,
        OutputLanguage.ES,
        model_name="quality-model",
    )
    assert base != build_linkedin_profile_generation_fingerprint(
        profile,
        market,
        OutputLanguage.EN,
        model_name="quality-model",
    )
    assert base != build_linkedin_profile_generation_fingerprint(
        profile,
        market,
        OutputLanguage.ES,
        model_name="other-model",
    )
    assert base != build_linkedin_profile_generation_fingerprint(
        profile,
        market,
        OutputLanguage.ES,
        model_name="quality-model",
        prompt_version="2.0",
    )
