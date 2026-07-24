from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs, replace_editorial_post


def test_editorial_plan_audit_rejects_clickbait_hook():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = replace_editorial_post(build_editorial_plan(), 0, hook="No vas a creer este secreto profesional")

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)

    assert audit.passed is False
    assert any("clickbait" in finding.message for finding in audit.findings)
