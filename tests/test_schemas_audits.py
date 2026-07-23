from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.audit_models import AuditFinding, LinkedInPositioningAudit
from schemas.enums import AuditSeverity, PriorityLevel
from schemas.examples import build_example_audit_report


def test_audit_scores_valid():
    audit = build_example_audit_report()

    assert audit.linkedin_positioning.overall_score <= 100
    assert audit.ats_estimation.overall_score <= 100


def test_audit_score_over_100_fails():
    data = build_example_audit_report().linkedin_positioning.model_dump()
    data["overall_score"] = 101

    with pytest.raises(ValidationError):
        LinkedInPositioningAudit.model_validate(data)


def test_audit_finding_valid():
    finding = AuditFinding(
        area="Headline",
        severity=AuditSeverity.WARNING,
        finding="Falta una keyword prioritaria.",
        recommendation="Agregar solo si existe evidencia.",
        priority=PriorityLevel.HIGH,
    )

    assert finding.area == "Headline"
