from __future__ import annotations

import pytest

from schemas.targeted_cv_models import TARGETED_CV_ATS_WEIGHTS
from services.targeted_cv_ats_audit_service import audit_targeted_cv_ats
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def test_targeted_cv_ats_audit_scores_with_fixed_weights():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)

    result = audit_targeted_cv_ats(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])

    assert result.job_index == 1
    assert 0 <= result.overall_score <= 100
    assert result.weights == TARGETED_CV_ATS_WEIGHTS
    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert set(result.component_scores) == set(TARGETED_CV_ATS_WEIGHTS)
    assert "Agile" in result.supported_keywords


def test_targeted_cv_ats_audit_flags_unsupported_keyword():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1).model_copy(update={"ats_keywords_used": ["Kubernetes"]})

    result = audit_targeted_cv_ats(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])

    assert "Kubernetes" in result.unsupported_keywords_removed
    assert result.findings
