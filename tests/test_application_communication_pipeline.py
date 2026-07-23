from __future__ import annotations

from services.application_communication_pipeline import run_application_communication_generation_pipeline
from services.openai_service import OpenAIService
from tests.application_communication_helpers import (
    build_application_communication_inputs,
    build_application_communication_kit,
)
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings


def test_pipeline_reuses_successful_kit_for_same_fingerprint():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)

    first = run_application_communication_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        "es",
        openai_service_factory=_factory_for(kit),
    )
    second = run_application_communication_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        "es",
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        openai_service_factory=_factory_for(kit),
    )

    assert first.result.success
    assert second.reused
    assert second.result.reused_from_session
    assert second.audit is not None
    assert second.redundancy_audit is not None


def test_pipeline_force_calls_model_again():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)
    client = FakeClient(FakeSDKResponse(kit))
    factory = lambda: OpenAIService(fake_settings(), client=client, prompt_loader=_prompt_loader)
    first = run_application_communication_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        "es",
        openai_service_factory=factory,
    )
    second = run_application_communication_generation_pipeline(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        "es",
        existing_result=first.result,
        existing_fingerprint=first.fingerprint,
        force=True,
        openai_service_factory=factory,
    )

    assert not second.reused
    assert len(client.responses.calls) == 2


def _factory_for(kit):
    return lambda: OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(kit)), prompt_loader=_prompt_loader)


def _prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema seguro para comunicaciones.",
        "generate_application_communications.txt": "Genera ApplicationCommunicationKit sin inventar evidencia.",
    }
    return prompts[filename]
