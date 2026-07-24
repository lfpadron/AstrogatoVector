from __future__ import annotations

from services.editorial_plan_service import EditorialPlanService, build_editorial_plan_input
from services.openai_service import OpenAIService
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs
from tests.linkedin_profile_helpers import FakeClient, FakeSDKResponse, fake_settings


def test_editorial_plan_service_generates_and_audits_structured_response():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    service = EditorialPlanService(
        OpenAIService(fake_settings(), client=FakeClient(FakeSDKResponse(build_editorial_plan()))),
        prompt_loader=_prompt_loader,
    )

    result = service.generate_editorial_plan(profile, market, compatibility, audit_report, "es")

    assert result.success is True
    assert result.audit_passed is True
    assert result.professional_brand_plan is not None
    assert result.professional_brand_plan.calendar.posts[0].hook


def test_editorial_plan_input_uses_reduced_structured_sections():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()

    text = build_editorial_plan_input(profile, market, compatibility, audit_report, "es")

    assert "<CANDIDATE_EVIDENCE>" in text
    assert "<TARGET_MARKET>" in text
    assert "<COMPATIBILITY>" in text
    assert "<POSITIONING_AUDIT>" in text
    assert "raw-cv" not in text.casefold()
    assert "openai-response" not in text.casefold()


def _prompt_loader(filename: str) -> str:
    return {
        "system_guardrails.txt": "Sistema con PLAN EDITORIAL PROFESIONAL y publicación automática bloqueada.",
        "generate_editorial_plan.txt": "Genera ProfessionalBrandPlan con 12 publicaciones sin inventar evidencia.",
    }[filename]
