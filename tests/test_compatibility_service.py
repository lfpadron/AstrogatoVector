from __future__ import annotations

from services.compatibility_service import CompatibilityService, build_compatibility_analysis_input
from services.openai_service import OpenAIService
from tests.compatibility_helpers import build_compatibility_inputs
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings


def _prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema seguro para compatibilidad.",
        "compatibility_analysis.txt": "Genera CompatibilitySemanticEvaluation sin score final.",
    }
    return prompts[filename]


def test_service_calls_openai_for_semantic_evaluation_and_scores_locally():
    profile, market, evaluation = build_compatibility_inputs()
    client = FakeClient(FakeSDKResponse(evaluation))
    service = CompatibilityService(OpenAIService(fake_settings(), client=client, prompt_loader=_prompt_loader), prompt_loader=_prompt_loader)

    result = service.analyze_compatibility(profile, market, "es")

    assert result.success is True
    assert result.compatibility_report is not None
    assert result.semantic_evaluation is not None
    assert result.audit_passed is True
    assert client.responses.calls[0]["text_format"].__name__ == "CompatibilitySemanticEvaluation"
    assert result.compatibility_report.job_compatibilities[0].compatibility_score == 100.0
    assert result.compatibility_report.job_compatibilities[1].compatibility_score < 100.0


def test_service_rejects_semantic_audit_failure_without_partial_outputs():
    profile, market, evaluation = build_compatibility_inputs()
    evaluation.job_evaluations[0].requirement_matches[0].requirement_name = "SAP"
    evaluation.job_evaluations[0].requirement_matches[0].normalized_requirement = "sap"
    client = FakeClient(FakeSDKResponse(evaluation))
    service = CompatibilityService(OpenAIService(fake_settings(), client=client, prompt_loader=_prompt_loader), prompt_loader=_prompt_loader)

    result = service.analyze_compatibility(profile, market, "es")

    assert result.success is False
    assert result.semantic_evaluation is None
    assert result.compatibility_report is None
    assert result.error_category == "compatibility_semantic_audit_failed"


def test_build_input_is_delimited_and_excludes_raw_later_outputs():
    profile, market, _ = build_compatibility_inputs()

    payload = build_compatibility_analysis_input(profile, market, "es")

    assert "<ASTROGATO_VECTOR_COMPATIBILITY_INPUT>" in payload
    assert "<CANDIDATE_EVIDENCE>" in payload
    assert "<JOB_ANALYSES>" in payload
    assert "LinkedInProfileOutput" not in payload
    assert "banner" not in payload.casefold()
    assert "API key" not in payload
