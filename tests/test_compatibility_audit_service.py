from __future__ import annotations

from services.compatibility_audit_service import audit_compatibility_report, audit_semantic_compatibility
from services.compatibility_scoring_service import CompatibilityScoringService
from tests.compatibility_helpers import build_compatibility_inputs


def test_semantic_audit_passes_for_valid_evaluation():
    profile, market, evaluation = build_compatibility_inputs()

    audit = audit_semantic_compatibility(evaluation, profile, market)

    assert audit.passed is True


def test_semantic_audit_rejects_invented_requirement():
    profile, market, evaluation = build_compatibility_inputs()
    evaluation.job_evaluations[0].requirement_matches[0].requirement_name = "SAP"
    evaluation.job_evaluations[0].requirement_matches[0].normalized_requirement = "sap"

    audit = audit_semantic_compatibility(evaluation, profile, market)

    assert audit.passed is False
    assert any("no aparece" in finding.message for finding in audit.findings)


def test_semantic_audit_rejects_missing_required_requirement():
    profile, market, evaluation = build_compatibility_inputs()
    evaluation.job_evaluations[0].requirement_matches = evaluation.job_evaluations[0].requirement_matches[1:]

    audit = audit_semantic_compatibility(evaluation, profile, market)

    assert audit.passed is False
    assert any("Falta evaluar el requisito obligatorio" in finding.message for finding in audit.findings)


def test_semantic_audit_rejects_invented_candidate_evidence():
    profile, market, evaluation = build_compatibility_inputs()
    evaluation.job_evaluations[0].requirement_matches[0].candidate_evidence[0].statement = "AWS y Kubernetes avanzados"

    audit = audit_semantic_compatibility(evaluation, profile, market)

    assert audit.passed is False
    assert any("evidencia declarada" in finding.message for finding in audit.findings)


def test_report_audit_rejects_bad_formula():
    profile, market, evaluation = build_compatibility_inputs()
    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    broken = report.model_copy(
        update={
            "job_compatibilities": [
                report.job_compatibilities[0].model_copy(update={"score_before_penalties": 10.0}),
                report.job_compatibilities[1],
            ]
        }
    )

    audit = audit_compatibility_report(broken, evaluation, market)

    assert audit.passed is False
    assert any("fórmula" in finding.message for finding in audit.findings)
