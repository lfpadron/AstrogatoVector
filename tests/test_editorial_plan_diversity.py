from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs, replace_editorial_post


def test_editorial_plan_audit_rejects_repeated_hooks_and_ctas():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = build_editorial_plan()
    plan = replace_editorial_post(plan, 1, hook=plan.calendar.posts[0].hook, cta=plan.calendar.posts[0].cta)

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)

    assert audit.passed is False
    assert any("hook" in finding.path for finding in audit.findings)
    assert any("cta" in finding.path for finding in audit.findings)
