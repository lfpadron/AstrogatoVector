from __future__ import annotations

from services.editorial_plan_audit_service import audit_editorial_plan
from tests.editorial_plan_helpers import build_editorial_plan, build_editorial_plan_inputs


def test_editorial_plan_audit_accepts_valid_plan():
    profile, market, compatibility, audit_report = build_editorial_plan_inputs()
    audit = audit_editorial_plan(build_editorial_plan(), profile, market, compatibility, audit_report)

    assert audit.passed is True
    assert audit.findings == []
    assert len(audit.character_counts) == 12
