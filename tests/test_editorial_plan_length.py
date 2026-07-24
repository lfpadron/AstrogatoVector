from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs, replace_editorial_post


def test_editorial_plan_audit_checks_declared_format_length():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    body = "Texto corto sin extensión suficiente."
    plan = replace_editorial_post(build_editorial_plan(), 0, body=body, character_count=len(body))

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)

    assert audit.passed is False
    assert any("debe tener entre" in finding.message for finding in audit.findings)
