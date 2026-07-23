from __future__ import annotations

import pytest

from schemas.enums import EvidenceStatus, PriorityLevel, RequirementCoverage, SkillCategory
from services.compatibility_scoring_service import (
    COVERAGE_POINTS,
    EVIDENCE_STATUS_FACTORS,
    CompatibilityScoringService,
)
from tests.compatibility_helpers import build_compatibility_inputs


def test_scoring_calculates_report_per_job_with_bands_and_gaps():
    profile, market, evaluation = build_compatibility_inputs()

    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)

    assert len(report.job_compatibilities) == 2
    assert report.highest_compatibility_job_index == 1
    assert report.job_compatibilities[0].compatibility_score > report.job_compatibilities[1].compatibility_score
    assert "Kubernetes" in " ".join(report.job_compatibilities[1].other_gaps + report.job_compatibilities[1].critical_gaps)
    assert report.average_compatibility_score == pytest.approx(
        round(sum(job.compatibility_score for job in report.job_compatibilities) / 2, 1)
    )


def test_dimension_without_requirements_is_not_zero_and_weight_is_redistributed():
    profile, market, evaluation = build_compatibility_inputs()

    job = CompatibilityScoringService().calculate_report(evaluation, market, profile).job_compatibilities[0]
    non_evaluated = [dimension for dimension in job.dimensions if not dimension.evaluated]

    assert non_evaluated
    assert all(dimension.score is None for dimension in non_evaluated)
    assert all(dimension.effective_weight == 0 for dimension in non_evaluated)
    assert sum(dimension.effective_weight for dimension in job.dimensions if dimension.evaluated) == pytest.approx(1.0)


def test_exact_two_requirement_formula_full_and_partial_equals_82_5():
    profile, market, evaluation = build_compatibility_inputs()
    evidence = profile.leadership_capabilities[0]
    for job_evaluation in evaluation.job_evaluations:
        job_evaluation.requirement_matches = [
            job_evaluation.requirement_matches[0].model_copy(
                update={
                    "requirement_name": "Agile",
                    "normalized_requirement": "agile",
                    "category": SkillCategory.BUSINESS,
                    "coverage": RequirementCoverage.FULL,
                    "candidate_evidence_status": EvidenceStatus.SUPPORTED,
                    "candidate_evidence": [evidence],
                    "matched_candidate_items": ["Agile"],
                    "missing_elements": [],
                    "priority": PriorityLevel.MEDIUM,
                    "required": True,
                }
            ),
            job_evaluation.requirement_matches[0].model_copy(
                update={
                    "requirement_name": "Business analysis",
                    "normalized_requirement": "business analysis",
                    "category": SkillCategory.BUSINESS,
                    "coverage": RequirementCoverage.PARTIAL,
                    "candidate_evidence_status": EvidenceStatus.SUPPORTED,
                    "candidate_evidence": [evidence],
                    "matched_candidate_items": ["análisis"],
                    "missing_elements": ["alcance"],
                    "priority": PriorityLevel.MEDIUM,
                    "required": True,
                }
            ),
        ]

    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)

    for job in report.job_compatibilities:
        evaluated_scores = [dimension.score for dimension in job.dimensions if dimension.evaluated]
        assert evaluated_scores == [82.5]
        assert job.score_before_penalties == 82.5


def test_indirect_inferred_factor_is_exact():
    assert COVERAGE_POINTS[RequirementCoverage.INDIRECT.value] * EVIDENCE_STATUS_FACTORS[EvidenceStatus.INFERRED.value] == pytest.approx(
        0.2625
    )


def test_critical_missing_penalty_is_capped_at_twenty():
    profile, market, evaluation = build_compatibility_inputs()
    for job_evaluation in evaluation.job_evaluations:
        base = job_evaluation.requirement_matches[0]
        job_evaluation.requirement_matches = [
            base.model_copy(
                update={
                    "requirement_name": f"Agile {index}",
                    "normalized_requirement": "agile",
                    "coverage": RequirementCoverage.MISSING,
                    "candidate_evidence_status": EvidenceStatus.MISSING,
                    "candidate_evidence": [],
                    "matched_candidate_items": [],
                    "missing_elements": ["sin evidencia"],
                    "priority": PriorityLevel.CRITICAL,
                    "required": True,
                }
            )
            for index in range(5)
        ]

    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)

    assert all(job.total_penalty == 20.0 for job in report.job_compatibilities)
    assert all(job.compatibility_score == 0.0 for job in report.job_compatibilities)


def test_seniority_gap_penalty_requires_two_levels():
    profile, market, evaluation = build_compatibility_inputs()
    profile.seniority = "mid"
    market.job_analyses[0].inferred_seniority = "director"
    market.job_analyses[1].inferred_seniority = "senior"

    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)

    assert any(p.penalty_type == "seniority_gap" for p in report.job_compatibilities[0].penalties)
    assert not any(p.penalty_type == "seniority_gap" for p in report.job_compatibilities[1].penalties)
