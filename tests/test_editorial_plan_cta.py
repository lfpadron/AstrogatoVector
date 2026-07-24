from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs, replace_editorial_post


def test_editorial_plan_audit_rejects_like_share_or_follow_cta():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = replace_editorial_post(build_editorial_plan(), 0, cta="Dale like y comparte este post.")

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)

    assert audit.passed is False
    assert any("likes" in finding.message or "shares" in finding.message for finding in audit.findings)
