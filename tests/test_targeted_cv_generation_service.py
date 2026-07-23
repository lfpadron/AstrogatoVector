from __future__ import annotations

from schemas.enums import OutputLanguage
from schemas.targeted_cv_models import TARGETED_CV_PROMPT_VERSION, TargetedCV
from services.openai_service import OpenAIService
from services.targeted_cv_generation_service import (
    TargetedCVGenerationService,
    build_targeted_cv_input,
)
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def test_generation_success_uses_quality_model_and_audits_output():
    profile, market, compatibility = build_targeted_cv_inputs()
    job = market.job_analyses[0]
    job_compatibility = compatibility.job_compatibilities[0]
    cv = build_targeted_cv(job.job_index)
    client = FakeClient(FakeSDKResponse(cv))
    service = TargetedCVGenerationService(
        OpenAIService(fake_settings(), client=client),
        prompt_loader=_prompt_loader,
    )

    result = service.generate_targeted_cv(profile, job, job_compatibility, OutputLanguage.ES)

    assert result.success
    assert result.targeted_cv == cv
    assert result.model_used == "quality-model"
    assert result.audit_passed
    assert result.prompt_version == TARGETED_CV_PROMPT_VERSION
    call = client.responses.calls[0]
    assert call["model"] == "quality-model"
    assert call["text_format"] is TargetedCV


def test_generation_input_is_delimited_without_generated_linkedin_content():
    profile, market, compatibility = build_targeted_cv_inputs()
    payload = build_targeted_cv_input(profile, market.job_analyses[0], compatibility.job_compatibilities[0], "es")

    assert "<ASTROGATO_VECTOR_TARGETED_CV>" in payload
    assert "<CANDIDATE_PROFESSIONAL_PROFILE>" in payload
    assert "<TARGET_JOB_ANALYSIS>" in payload
    assert "<JOB_COMPATIBILITY>" in payload
    assert "LinkedInProfileOutput" not in payload
    assert "headline" not in payload.casefold()
    assert "raw_response" not in payload


def test_generation_audit_failure_blocks_unsupported_keyword():
    profile, market, compatibility = build_targeted_cv_inputs()
    bad = build_targeted_cv(1).model_copy(update={"ats_keywords_used": ["Kubernetes"]})
    service = TargetedCVGenerationService(
        OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(bad))),
        prompt_loader=_prompt_loader,
    )

    result = service.generate_targeted_cv(profile, market.job_analyses[0], compatibility.job_compatibilities[0], "es")

    assert not result.success
    assert result.targeted_cv is None
    assert result.error_category == "targeted_cv_audit_failed"
    assert any("respaldada" in finding for finding in result.audit_findings)


def _prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema seguro para CV por vacante.",
        "generate_targeted_cv.txt": "Genera TargetedCV sin inventar evidencia.",
    }
    return prompts[filename]
