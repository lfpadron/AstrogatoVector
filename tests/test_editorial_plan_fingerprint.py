from __future__ import annotations

from services.editorial_plan_service import build_editorial_plan_input_fingerprint
from tests.editorial_plan_helpers import build_editorial_plan_inputs


def test_editorial_plan_fingerprint_changes_with_language():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()

    first = build_editorial_plan_input_fingerprint(
        profile,
        market,
        compatibility,
        audit_report,
        "es",
        model_name="quality-model",
    )
    second = build_editorial_plan_input_fingerprint(
        profile,
        market,
        compatibility,
        audit_report,
        "en",
        model_name="quality-model",
    )

    assert first != second
    assert len(first) == 64
