from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs, replace_editorial_post


def test_editorial_plan_audit_rejects_market_gap_as_experience():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = build_editorial_plan()
    body = plan.calendar.posts[0].body + " Además, domino Kubernetes en proyectos productivos."
    plan = replace_editorial_post(plan, 0, body=body, character_count=len(body.strip()))

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)

    assert audit.passed is False
    assert any("experiencia demostrada" in finding.message for finding in audit.findings)
