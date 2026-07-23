from __future__ import annotations

from schemas.application_communication_models import (
    APPLICATION_COMMUNICATION_PROMPT_VERSION,
    ApplicationCommunicationKit,
)
from schemas.enums import OutputLanguage
from services.application_communication_service import (
    ApplicationCommunicationService,
    build_application_communication_input,
)
from services.openai_service import OpenAIService
from tests.application_communication_helpers import (
    build_application_communication_inputs,
    build_application_communication_kit,
)
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings


def test_generation_success_uses_quality_model_and_audits_output():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    job = market.job_analyses[0]
    job_compatibility = compatibility.job_compatibilities[0]
    kit = build_application_communication_kit(job.job_index)
    client = FakeClient(FakeSDKResponse(kit))
    service = ApplicationCommunicationService(
        OpenAIService(fake_settings(), client=client),
        prompt_loader=_prompt_loader,
    )

    result = service.generate_communication_kit(profile, job, job_compatibility, targeted_cvs[1], OutputLanguage.ES)

    assert result.success
    assert result.communication_kit == kit
    assert result.model_used == "quality-model"
    assert result.audit_passed
    assert result.redundancy_audit_passed
    assert result.prompt_version == APPLICATION_COMMUNICATION_PROMPT_VERSION
    call = client.responses.calls[0]
    assert call["model"] == "quality-model"
    assert call["text_format"] is ApplicationCommunicationKit


def test_generation_input_is_delimited_without_raw_or_linkedin_content():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    payload = build_application_communication_input(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        "es",
    )

    assert "<ASTROGATO_VECTOR_APPLICATION_COMMUNICATION>" in payload
    assert "<CANDIDATE_EVIDENCE>" in payload
    assert "<TARGET_JOB>" in payload
    assert "<COMPATIBILITY>" in payload
    assert "<TARGETED_CV_SUMMARY>" in payload
    assert "LinkedInProfileOutput" not in payload
    assert "raw_response" not in payload
    assert "headline" not in payload.casefold()


def test_generation_audit_failure_blocks_placeholder_greeting():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)
    bad_cover = kit.cover_letter.model_copy(update={"greeting": "Estimado/a [Nombre]:"})
    bad = kit.model_copy(update={"cover_letter": bad_cover})
    service = ApplicationCommunicationService(
        OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(bad))),
        prompt_loader=_prompt_loader,
    )

    result = service.generate_communication_kit(
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
        "es",
    )

    assert not result.success
    assert result.communication_kit is None
    assert result.error_category == "application_communication_audit_failed"
    assert any("placeholder" in finding for finding in result.audit_findings)


def _prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema seguro para comunicaciones.",
        "generate_application_communications.txt": "Genera ApplicationCommunicationKit sin inventar evidencia.",
    }
    return prompts[filename]
