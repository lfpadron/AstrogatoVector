"""Deterministic validation for final LinkedIn and ATS audit reports."""

from __future__ import annotations

from schemas.audit_models import (
    ALLOWED_AUDIT_CATEGORIES,
    ATS_AUDIT_COMPONENT_WEIGHTS,
    LINKEDIN_AUDIT_COMPONENT_WEIGHTS,
    AuditFinding,
    AuditReport,
    FinalAuditValidationFinding,
    FinalAuditValidationResult,
)

GENERIC_RECOMMENDATIONS = {
    "mejora tu perfil",
    "mejorar perfil",
    "optimiza tu linkedin",
    "improve your profile",
}
ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}


def audit_final_report(report: AuditReport) -> FinalAuditValidationResult:
    """Validate a final audit report before it is stored or shown."""
    findings: list[FinalAuditValidationFinding] = []
    if not report.success:
        return FinalAuditValidationResult(passed=True, findings=[])

    if report.linkedin_positioning is None:
        _add_error(findings, "linkedin_positioning", "La auditoría de LinkedIn es obligatoria.")
    if report.ats_estimation is None:
        _add_error(findings, "ats_estimation", "La auditoría ATS es obligatoria.")
    if report.linkedin_positioning is None or report.ats_estimation is None:
        return FinalAuditValidationResult(passed=False, findings=findings)

    _audit_component_math(
        report.linkedin_positioning.components,
        LINKEDIN_AUDIT_COMPONENT_WEIGHTS,
        report.linkedin_positioning.score,
        "linkedin_positioning",
        findings,
    )
    _audit_component_math(
        report.ats_estimation.components,
        ATS_AUDIT_COMPONENT_WEIGHTS,
        report.ats_estimation.score,
        "ats_estimation",
        findings,
    )
    _audit_finding_group(report.findings, "findings", findings)
    _audit_finding_group(report.strengths, "strengths", findings)
    _audit_finding_group(report.risks, "risks", findings)
    _audit_finding_group(report.linkedin_positioning.findings, "linkedin_positioning.findings", findings)
    _audit_finding_group(report.ats_estimation.findings, "ats_estimation.findings", findings)
    _audit_recommendations(report.recommendations, "recommendations", findings)
    _audit_recommendations(report.quick_wins, "quick_wins", findings)

    if report.quick_wins and any(recommendation.priority != "Quick Wins" for recommendation in report.quick_wins):
        _add_error(findings, "quick_wins", "Todas las acciones Quick Wins deben tener prioridad Quick Wins.")
    if report.overall_score is not None:
        expected = round((report.linkedin_positioning.score + report.ats_estimation.score) / 2, 1)
        if abs(report.overall_score - expected) > 0.11:
            _add_error(findings, "overall_score", "El score global debe promediar LinkedIn y ATS.")

    return FinalAuditValidationResult(
        passed=not any(finding.severity == "error" for finding in findings),
        findings=findings,
    )


def _audit_component_math(
    components: list,
    weights: dict[str, float],
    score: float,
    path: str,
    findings: list[FinalAuditValidationFinding],
) -> None:
    names = [component.name for component in components]
    if set(names) != set(weights):
        _add_error(findings, f"{path}.components", "Los componentes no coinciden con la metodología requerida.")
    if len(names) != len(set(names)):
        _add_error(findings, f"{path}.components", "Hay componentes duplicados.")
    for component in components:
        expected_weight = weights.get(component.name)
        if expected_weight is None:
            continue
        if abs(component.weight - expected_weight) > 0.000001:
            _add_error(findings, f"{path}.components.{component.name}", "El peso del componente no coincide.")
    expected_score = round(sum(component.score * component.weight for component in components), 1)
    if abs(score - expected_score) > 0.11:
        _add_error(findings, f"{path}.score", "El score no coincide con la suma ponderada de componentes.")


def _audit_finding_group(
    audit_findings: list[AuditFinding],
    path: str,
    findings: list[FinalAuditValidationFinding],
) -> None:
    seen = set()
    for index, finding in enumerate(audit_findings):
        if finding.severity not in ALLOWED_SEVERITIES:
            _add_error(findings, f"{path}[{index}].severity", "La severidad no está permitida.")
        if finding.category not in ALLOWED_AUDIT_CATEGORIES:
            _add_error(findings, f"{path}[{index}].category", "La categoría no está permitida.")
        if finding.recommendation.casefold().strip() in GENERIC_RECOMMENDATIONS:
            _add_error(findings, f"{path}[{index}].recommendation", "La recomendación no es accionable.")
        key = (finding.severity, finding.category, finding.title.casefold(), finding.description.casefold())
        if key in seen:
            _add_warning(findings, f"{path}[{index}]", "Hallazgo duplicado.")
        seen.add(key)


def _audit_recommendations(
    recommendations: list,
    path: str,
    findings: list[FinalAuditValidationFinding],
) -> None:
    seen = set()
    for index, recommendation in enumerate(recommendations):
        if recommendation.category not in ALLOWED_AUDIT_CATEGORIES:
            _add_error(findings, f"{path}[{index}].category", "La categoría de recomendación no está permitida.")
        if recommendation.action.casefold().strip() in GENERIC_RECOMMENDATIONS:
            _add_error(findings, f"{path}[{index}].action", "La acción recomendada no es específica.")
        key = (recommendation.priority, recommendation.category, recommendation.action.casefold())
        if key in seen:
            _add_warning(findings, f"{path}[{index}]", "Recomendación duplicada.")
        seen.add(key)


def _add_error(findings: list[FinalAuditValidationFinding], path: str, message: str) -> None:
    findings.append(FinalAuditValidationFinding(severity="error", path=path, message=message))


def _add_warning(findings: list[FinalAuditValidationFinding], path: str, message: str) -> None:
    findings.append(FinalAuditValidationFinding(severity="warning", path=path, message=message))
