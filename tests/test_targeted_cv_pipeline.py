from __future__ import annotations

from services.openai_service import OpenAIService
from services.targeted_cv_pipeline import run_targeted_cv_generation_pipeline
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def test_pipeline_reuses_successful_targeted_cv_for_same_fingerprint():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)

    first = run_targeted_cv_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "es",
        openai_service_factory=_factory_for(cv),
    )
    second = run_targeted_cv_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "es",
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        openai_service_factory=_factory_for(cv),
    )

    assert first.result.success
    assert second.reused
    assert second.result.reused_from_session
    assert second.ats_audit is not None


def test_pipeline_force_calls_model_again():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)
    client = FakeClient(FakeSDKResponse(cv))
    first = run_targeted_cv_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "es",
        openai_service_factory=lambda: OpenAIService(fake_settings(), client=client, prompt_loader=_prompt_loader),
    )
    second = run_targeted_cv_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        "es",
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        force=True,
        openai_service_factory=lambda: OpenAIService(fake_settings(), client=client, prompt_loader=_prompt_loader),
    )

    assert not second.reused
    assert len(client.responses.calls) == 2


def _factory_for(cv):
    return lambda: OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(cv)), prompt_loader=_prompt_loader)


def _prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema seguro para CV por vacante.",
        "generate_targeted_cv.txt": "Genera TargetedCV sin inventar evidencia.",
    }
    return prompts[filename]
