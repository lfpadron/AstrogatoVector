from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.compatibility_models import CompatibilityReport, JobCompatibility, compatibility_band_for_score
from schemas.examples import build_example_compatibility_report


def test_job_compatibility_six_dimensions_valid():
    report = build_example_compatibility_report()
    job = report.job_compatibilities[0]

    assert len(job.dimensions) == 6
    assert sum(d.original_weight for d in job.dimensions) == pytest.approx(1.0)
    assert sum(d.effective_weight for d in job.dimensions if d.evaluated) == pytest.approx(1.0)
    assert job.compatibility_score == pytest.approx(job.score_before_penalties - job.total_penalty)
    assert job.compatibility_band == compatibility_band_for_score(job.compatibility_score)


def test_job_compatibility_missing_dimension_fails():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["dimensions"] = data["dimensions"][:5]

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_job_compatibility_wrong_original_weight_fails():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["dimensions"][0]["original_weight"] = 0.31
    data["dimensions"][1]["original_weight"] = 0.24

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_job_compatibility_effective_weights_sum_distinct_from_one_fails():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["dimensions"][0]["effective_weight"] = 0.25

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_job_compatibility_non_evaluated_dimension_requires_none_score():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["dimensions"][0]["evaluated"] = False
    data["dimensions"][0]["score"] = 70
    data["dimensions"][0]["effective_weight"] = 0

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_job_compatibility_score_before_penalties_incorrect_fails():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["score_before_penalties"] += 5
    data["compatibility_score"] += 5

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_job_compatibility_total_penalty_incorrect_fails():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["penalties"] = [
        {
            "penalty_type": "critical_required_missing",
            "points": 5.0,
            "reason": "Requisito crítico obligatorio no respaldado: PMP.",
            "related_requirement": "PMP",
        }
    ]
    data["total_penalty"] = 0.0

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_job_compatibility_final_score_incorrect_fails():
    data = build_example_compatibility_report().job_compatibilities[0].model_dump()
    data["compatibility_score"] += 5

    with pytest.raises(ValidationError):
        JobCompatibility.model_validate(data)


def test_compatibility_report_highest_match_missing_fails():
    data = build_example_compatibility_report().model_dump()
    data["highest_compatibility_job_index"] = 6

    with pytest.raises(ValidationError):
        CompatibilityReport.model_validate(data)


def test_compatibility_report_duplicate_indices_fail():
    data = build_example_compatibility_report().model_dump()
    data["job_compatibilities"][1]["job_index"] = 1

    with pytest.raises(ValidationError):
        CompatibilityReport.model_validate(data)


def test_compatibility_report_average_incorrect_fails():
    data = build_example_compatibility_report().model_dump()
    data["average_compatibility_score"] += 3

    with pytest.raises(ValidationError):
        CompatibilityReport.model_validate(data)
