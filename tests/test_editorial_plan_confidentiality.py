from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs, replace_editorial_post


def test_editorial_plan_audit_blocks_confidential_content():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    plan = replace_editorial_post(
        build_editorial_plan(),
        0,
        notes=["Caso con cliente Acme y presupuesto interno de $5000."],
    )

    audit = audit_editorial_plan(plan, profile, market, compatibility, audit_report)

    assert audit.passed is False
    assert any("confidencial" in finding.message for finding in audit.findings)
