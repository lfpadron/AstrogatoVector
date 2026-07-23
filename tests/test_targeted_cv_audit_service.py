from __future__ import annotations

from schemas.enums import EvidenceStatus
from services.targeted_cv_audit_service import audit_targeted_cv
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def test_targeted_cv_audit_accepts_evidence_backed_cv():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)

    result = audit_targeted_cv(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])

    assert result.passed
    assert not any(finding.severity == "error" for finding in result.findings)
    assert any(finding.path == "header.candidate_name" for finding in result.findings)


def test_targeted_cv_audit_rejects_unsupported_skill_and_metric():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)
    bad_skill = cv.skills[0].model_copy(update={"name": "Kubernetes", "evidence_status": EvidenceStatus.MISSING})
    bad_bullet = cv.experience[0].bullets[0].model_copy(update={"text": "Logró una mejora inventada de 99%."})
    bad_experience = cv.experience[0].model_copy(update={"bullets": [bad_bullet]})
    cv = cv.model_copy(update={"skills": [bad_skill, *cv.skills[1:]], "experience": [bad_experience]})

    result = audit_targeted_cv(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "MISSING" in messages
    assert "99%" in messages
