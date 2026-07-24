from __future__ import annotations

from services.editorial_plan_pipeline import (
    EDITORIAL_PLAN_CONFIGURATION_MESSAGE,
    run_editorial_plan_generation_pipeline,
)
from services.openai_config import OpenAIConfigurationError
from tests.editorial_plan_helpers import build_editorial_plan_inputs


def test_editorial_plan_pipeline_returns_safe_configuration_error():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()

    run = run_editorial_plan_generation_pipeline(
        profile,
        market,
        compatibility,
        audit_report,
        "es",
        openai_service_factory=lambda: (_ for _ in ()).throw(OpenAIConfigurationError(errors=["missing key"])),
    )

    assert run.result.success is False
    assert run.result.user_message == EDITORIAL_PLAN_CONFIGURATION_MESSAGE
    assert "missing key" in run.result.warnings
