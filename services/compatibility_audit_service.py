"""Deterministic audits for semantic compatibility and score reports."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from pydantic import ValidationError

from schemas.compatibility_analysis_models import (
    CompatibilityAuditFinding,
    CompatibilityAuditResult,
    CompatibilitySemanticEvaluation,
    JobCompatibilitySemanticEvaluation,
    SemanticRequirementMatch,
)
from schemas.compatibility_models import (
    ALLOWED_PENALTY_TYPES,
    COMPATIBILITY_DIMENSION_WEIGHTS,
    COMPATIBILITY_METHODOLOGY_VERSION,
    SCORE_TOLERANCE,
    CompatibilityReport,
    compatibility_band_for_score,
)
from schemas.enums import EvidenceStatus, PriorityLevel, RequirementCoverage
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.market_models import JobAnalysis, JobRequirement, TargetMarketAnalysis

SEMANTIC_AUDIT_EVIDENCE_ERROR_MESSAGE = (
    "La evaluación fue recibida, pero no superó la validación de evidencia.\n\n"
    "No se mostrarán scores porque una o más correspondencias no pudieron comprobarse con el perfil profesional."
)
MATH_AUDIT_ERROR_MESSAGE = (
    "No fue posible validar el cálculo de compatibilidad. No se mostrarán resultados parciales."
)


def audit_semantic_compatibility(
    evaluation: CompatibilitySemanticEvaluation,
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
) -> CompatibilityAuditResult:
    """Audit correspondence, coverage and evidence in the semantic evaluation."""
    findings: list[CompatibilityAuditFinding] = []
    expected_indices = {job.job_index for job in market_analysis.job_analyses}
    job_by_index = {job.job_index: job for job in market_analysis.job_analyses}
    evaluation_by_index = {job.job_index: job for job in evaluation.job_evaluations}
    evidence_catalog = _CandidateEvidenceCatalog(candidate_profile)

    _audit_job_indices(evaluation, expected_indices, findings)
    for job_index in sorted(expected_indices):
        job = job_by_index[job_index]
        job_evaluation = evaluation_by_index.get(job_index)
        if job_evaluation is None:
            continue
        _audit_job_header(job_evaluation, job, findings)
        _audit_requirement_correspondence(job_evaluation, job, findings)
        _audit_requirement_coverages(job_evaluation, findings)
        _audit_candidate_evidence(job_evaluation, evidence_catalog, findings)

    passed = not any(finding.severity == "error" for finding in findings)
    return CompatibilityAuditResult(passed=passed, findings=findings)


def audit_compatibility_report(
    report: CompatibilityReport,
    evaluation: CompatibilitySemanticEvaluation,
    market_analysis: TargetMarketAnalysis,
) -> CompatibilityAuditResult:
    """Audit mathematical consistency and report/evaluation correspondence."""
    findings: list[CompatibilityAuditFinding] = []
    try:
        CompatibilityReport.model_validate(report.model_dump())
    except ValidationError as exc:
        _add_error(findings, "report", f"El reporte no cumple el contrato Pydantic: {exc.errors()[0]['msg']}")

    expected_indices = {job.job_index for job in market_analysis.job_analyses}
    report_indices = {job.job_index for job in report.job_compatibilities}
    evaluation_indices = {job.job_index for job in evaluation.job_evaluations}
    if report_indices != expected_indices:
        _add_error(findings, "job_compatibilities", "El reporte no contiene exactamente una compatibilidad por vacante.")
    if report_indices != evaluation_indices:
        _add_error(findings, "job_compatibilities", "El reporte no corresponde a la evaluación semántica recibida.")

    for job in report.job_compatibilities:
        path = f"job_compatibilities[{job.job_index}]"
        _audit_dimensions(job, path, findings)
        _audit_penalties(job, path, findings)
        _audit_job_math(job, path, findings)
        if job.confidence < 0.5:
            _add_warning(findings, f"{path}.confidence", "La confianza general es baja y requiere revisión humana.")

    _audit_report_math(report, findings)
    passed = not any(finding.severity == "error" for finding in findings)
    return CompatibilityAuditResult(passed=passed, findings=findings)


def _audit_job_indices(
    evaluation: CompatibilitySemanticEvaluation,
    expected_indices: set[int],
    findings: list[CompatibilityAuditFinding],
) -> None:
    actual_indices = [job.job_index for job in evaluation.job_evaluations]
    actual_set = set(actual_indices)
    if len(evaluation.job_evaluations) < 2 or len(evaluation.job_evaluations) > 6:
        _add_error(findings, "job_evaluations", "El número de evaluaciones debe estar entre dos y seis.")
    if len(actual_indices) != len(actual_set):
        _add_error(findings, "job_evaluations", "Los índices de evaluación deben ser únicos.")
    for missing in sorted(expected_indices - actual_set):
        _add_error(findings, "job_evaluations", f"Falta la evaluación de la vacante {missing}.")
    for extra in sorted(actual_set - expected_indices):
        _add_error(findings, "job_evaluations", f"Existe una evaluación para una vacante no recibida: {extra}.")


def _audit_job_header(
    job_evaluation: JobCompatibilitySemanticEvaluation,
    job: JobAnalysis,
    findings: list[CompatibilityAuditFinding],
) -> None:
    path = f"job_evaluations[{job_evaluation.job_index}]"
    if not _titles_correspond(job.title, job_evaluation.job_title):
        _add_error(findings, f"{path}.job_title", "El título evaluado no corresponde a la vacante.")
    if job.company and not _company_corresponds(job.company, job_evaluation.company):
        _add_error(findings, f"{path}.company", "La empresa evaluada no corresponde a la vacante.")


def _audit_requirement_correspondence(
    job_evaluation: JobCompatibilitySemanticEvaluation,
    job: JobAnalysis,
    findings: list[CompatibilityAuditFinding],
) -> None:
    path = f"job_evaluations[{job_evaluation.job_index}].requirement_matches"
    if not job_evaluation.requirement_matches:
        _add_error(findings, path, "La vacante no tiene requisitos evaluados.")
        return

    allowed = _AllowedRequirementCatalog(job)
    seen: set[str] = set()
    for index, match in enumerate(job_evaluation.requirement_matches):
        match_path = f"{path}[{index}]"
        key = _normalize_key(match.normalized_requirement)
        if key in seen:
            _add_error(findings, match_path, "Se detectó un requisito duplicado en la evaluación.")
        seen.add(key)
        if not allowed.contains(match.requirement_name, match.normalized_requirement):
            _add_error(findings, match_path, "El requisito evaluado no aparece en el análisis estructurado de la vacante.")

    for requirement in job.requirements:
        if requirement.required and not any(_requirement_matches(match, requirement) for match in job_evaluation.requirement_matches):
            _add_error(
                findings,
                path,
                f"Falta evaluar el requisito obligatorio: {requirement.name}.",
            )


def _audit_requirement_coverages(
    job_evaluation: JobCompatibilitySemanticEvaluation,
    findings: list[CompatibilityAuditFinding],
) -> None:
    for index, match in enumerate(job_evaluation.requirement_matches):
        path = f"job_evaluations[{job_evaluation.job_index}].requirement_matches[{index}]"
        coverage = _enum_value(match.coverage)
        status = _enum_value(match.candidate_evidence_status)
        if coverage == RequirementCoverage.FULL.value:
            if not match.candidate_evidence:
                _add_error(findings, path, "FULL debe incluir evidencia del candidato.")
            if status != EvidenceStatus.SUPPORTED.value:
                _add_error(findings, path, "FULL exige EvidenceStatus SUPPORTED.")
            if not match.matched_candidate_items:
                _add_error(findings, path, "FULL debe indicar matched_candidate_items.")
            if match.confidence < 0.5:
                _add_warning(findings, path, "FULL con confianza menor a 0.50 requiere revisión.")
        elif coverage == RequirementCoverage.PARTIAL.value:
            if not match.candidate_evidence:
                _add_error(findings, path, "PARTIAL debe incluir evidencia presente.")
            if not match.matched_candidate_items or not match.missing_elements:
                _add_error(findings, path, "PARTIAL debe indicar qué se cubre y qué falta.")
        elif coverage == RequirementCoverage.INDIRECT.value:
            if not match.matched_candidate_items:
                _add_error(findings, path, "INDIRECT debe indicar experiencia transferible.")
            if not match.missing_elements:
                _add_warning(findings, path, "INDIRECT debería explicar qué falta como evidencia directa.")
        elif coverage == RequirementCoverage.MISSING.value:
            if match.candidate_evidence:
                _add_error(findings, path, "MISSING no debe contener evidencia como respaldo.")
            if status != EvidenceStatus.MISSING.value:
                _add_error(findings, path, "MISSING debe conservar EvidenceStatus MISSING.")
        elif coverage == RequirementCoverage.CONFLICT.value:
            if status != EvidenceStatus.CONFLICT.value:
                _add_error(findings, path, "CONFLICT debe conservar EvidenceStatus CONFLICT.")
            if not match.explanation:
                _add_error(findings, path, "CONFLICT debe explicar la contradicción.")
        elif coverage == RequirementCoverage.NOT_APPLICABLE.value and match.required:
            _add_error(findings, path, "NOT_APPLICABLE no debe usarse para evitar un requisito obligatorio.")


def _audit_candidate_evidence(
    job_evaluation: JobCompatibilitySemanticEvaluation,
    evidence_catalog: "_CandidateEvidenceCatalog",
    findings: list[CompatibilityAuditFinding],
) -> None:
    for match_index, match in enumerate(job_evaluation.requirement_matches):
        for evidence_index, evidence in enumerate(match.candidate_evidence):
            path = (
                f"job_evaluations[{job_evaluation.job_index}].requirement_matches"
                f"[{match_index}].candidate_evidence[{evidence_index}]"
            )
            if not evidence_catalog.contains_evidence_item(evidence):
                _add_error(findings, path, "La evidencia declarada no pudo localizarse en el perfil profesional.")
            for reference in evidence.references:
                if not evidence_catalog.contains_reference(reference):
                    _add_error(findings, path, "La referencia de evidencia no corresponde al perfil profesional.")


def _audit_dimensions(job, path: str, findings: list[CompatibilityAuditFinding]) -> None:
    dimensions = job.dimensions
    if len(dimensions) != 6:
        _add_error(findings, f"{path}.dimensions", "Deben existir exactamente seis dimensiones.")
    original_sum = sum(dimension.original_weight for dimension in dimensions)
    if abs(original_sum - 1.0) > 0.000001:
        _add_error(findings, f"{path}.dimensions", "Los pesos originales deben sumar 1.0.")
    evaluated = [dimension for dimension in dimensions if dimension.evaluated]
    effective_sum = sum(dimension.effective_weight for dimension in evaluated)
    if evaluated and abs(effective_sum - 1.0) > 0.001:
        _add_error(findings, f"{path}.dimensions", "Los pesos efectivos deben sumar 1.0 entre dimensiones evaluadas.")
    for index, dimension in enumerate(dimensions):
        dim_path = f"{path}.dimensions[{index}]"
        if dimension.dimension_id not in COMPATIBILITY_DIMENSION_WEIGHTS:
            _add_error(findings, dim_path, "La dimensión no pertenece a la metodología vigente.")
        if not dimension.evaluated and dimension.score is not None:
            _add_error(findings, dim_path, "Una dimensión no evaluada debe tener score=None.")
        if dimension.evaluated and dimension.score is None:
            _add_error(findings, dim_path, "Una dimensión evaluada debe tener score.")
        if dimension.score is not None and not _is_finite_between(dimension.score, 0.0, 100.0):
            _add_error(findings, dim_path, "El score de dimensión debe estar entre 0 y 100.")


def _audit_penalties(job, path: str, findings: list[CompatibilityAuditFinding]) -> None:
    seen = set()
    critical_total = 0.0
    for index, penalty in enumerate(job.penalties):
        penalty_path = f"{path}.penalties[{index}]"
        key = (penalty.penalty_type, penalty.related_requirement)
        if key in seen:
            _add_error(findings, penalty_path, "Se detectó una penalización duplicada.")
        seen.add(key)
        if penalty.penalty_type not in ALLOWED_PENALTY_TYPES:
            _add_error(findings, penalty_path, "La penalización no está permitida.")
        if penalty.points < 0:
            _add_error(findings, penalty_path, "La penalización no puede ser negativa.")
        if penalty.penalty_type == "critical_required_missing":
            critical_total += penalty.points
            related = penalty.related_requirement or ""
            match = _find_match(job.requirement_matches, related)
            if match is None:
                _add_error(findings, penalty_path, "La penalización crítica no referencia un requisito evaluado.")
            elif not (
                match.required
                and match.priority == PriorityLevel.CRITICAL.value
                and match.coverage in {RequirementCoverage.MISSING.value, RequirementCoverage.CONFLICT.value}
            ):
                _add_error(findings, penalty_path, "La penalización crítica no cumple las reglas de criticidad.")
    if critical_total > 20.0:
        _add_error(findings, f"{path}.penalties", "La penalización crítica acumulada no puede superar 20 puntos.")


def _audit_job_math(job, path: str, findings: list[CompatibilityAuditFinding]) -> None:
    expected_before = round(sum((dimension.score or 0.0) * dimension.effective_weight for dimension in job.dimensions), 1)
    if abs(job.score_before_penalties - expected_before) > SCORE_TOLERANCE:
        _add_error(findings, f"{path}.score_before_penalties", "El score antes de penalización no coincide con la fórmula.")
    expected_penalty = round(sum(penalty.points for penalty in job.penalties), 1)
    if abs(job.total_penalty - expected_penalty) > SCORE_TOLERANCE:
        _add_error(findings, f"{path}.total_penalty", "La penalización total no coincide con las penalizaciones.")
    expected_final = round(max(0.0, min(100.0, job.score_before_penalties - job.total_penalty)), 1)
    if abs(job.compatibility_score - expected_final) > SCORE_TOLERANCE:
        _add_error(findings, f"{path}.compatibility_score", "El score final no coincide con la fórmula.")
    if compatibility_band_for_score(job.compatibility_score) != job.compatibility_band:
        _add_error(findings, f"{path}.compatibility_band", "La banda no corresponde al score.")
    for field_name in ("compatibility_score", "score_before_penalties", "total_penalty", "confidence"):
        value = getattr(job, field_name)
        if not math.isfinite(value):
            _add_error(findings, f"{path}.{field_name}", "El valor no puede ser NaN ni infinito.")


def _audit_report_math(report: CompatibilityReport, findings: list[CompatibilityAuditFinding]) -> None:
    if report.methodology_version != COMPATIBILITY_METHODOLOGY_VERSION:
        _add_error(findings, "methodology_version", "La versión de metodología no corresponde a la vigente.")
    average = round(sum(job.compatibility_score for job in report.job_compatibilities) / len(report.job_compatibilities), 1)
    if abs(report.average_compatibility_score - average) > SCORE_TOLERANCE:
        _add_error(findings, "average_compatibility_score", "El promedio de compatibilidad no coincide.")
    highest = max(report.job_compatibilities, key=lambda job: (job.compatibility_score, -job.job_index)).job_index
    if report.highest_compatibility_job_index != highest:
        _add_error(findings, "highest_compatibility_job_index", "La vacante de mayor alineación no coincide.")
    if not math.isfinite(report.average_compatibility_score):
        _add_error(findings, "average_compatibility_score", "El promedio no puede ser NaN ni infinito.")


class _AllowedRequirementCatalog:
    def __init__(self, job: JobAnalysis) -> None:
        values: list[str] = []
        for requirement in job.requirements:
            values.extend([requirement.name, requirement.normalized_name])
            values.extend(requirement.exact_keywords)
        values.extend(job.responsibilities)
        values.extend(job.technical_skills)
        values.extend(job.soft_skills)
        values.extend(job.leadership_skills)
        values.extend(job.tools_and_technologies)
        values.extend(job.industries)
        values.extend(job.education_requirements)
        values.extend(job.language_requirements)
        values.extend(job.certifications)
        self._keys = {_normalize_key(value) for value in values if value}

    def contains(self, name: str, normalized: str) -> bool:
        candidates = [_normalize_key(name), _normalize_key(normalized)]
        return any(_phrase_or_tokens_found(candidate, self._keys) for candidate in candidates if candidate)


class _CandidateEvidenceCatalog:
    def __init__(self, profile: CandidateProfessionalProfile) -> None:
        self._statements: set[str] = set()
        self._references: set[tuple[str, str]] = set()
        self._add_text(profile.professional_identity)
        self._add_text(profile.summary)
        for value in [*profile.targetable_roles, *profile.industries, *profile.ambiguities, *profile.conflicts]:
            self._add_text(value)
        for skill in profile.skills:
            self._add_skill(skill)
        for item in profile.leadership_capabilities + profile.education + profile.certifications + profile.languages:
            self._add_evidence_item(item)
        for achievement in profile.achievements:
            self._add_achievement(achievement)
        for employment in profile.employment_history:
            self._add_employment(employment)

    def contains_evidence_item(self, item: EvidenceItem) -> bool:
        statement = _normalize_key(item.statement)
        if statement in self._statements:
            return True
        return _phrase_or_tokens_found(statement, self._statements)

    def contains_reference(self, reference: EvidenceReference) -> bool:
        key = (_normalize_key(reference.source_section), _normalize_key(reference.source_excerpt))
        if key in self._references:
            return True
        excerpt = key[1]
        return any(excerpt and (excerpt in stored_excerpt or stored_excerpt in excerpt) for _, stored_excerpt in self._references)

    def _add_employment(self, employment: EmploymentEntry) -> None:
        self._add_text(employment.employer)
        self._add_text(employment.role_title)
        for value in employment.industries:
            self._add_text(value)
        for item in employment.responsibilities:
            self._add_evidence_item(item)
        for achievement in employment.achievements:
            self._add_achievement(achievement)
        for skill in employment.technologies:
            self._add_skill(skill)

    def _add_skill(self, skill: CandidateSkill) -> None:
        self._add_text(skill.name)
        self._add_text(skill.normalized_name)
        for reference in skill.references:
            self._add_reference(reference)

    def _add_evidence_item(self, item: EvidenceItem) -> None:
        self._add_text(item.statement)
        if item.notes:
            self._add_text(item.notes)
        for reference in item.references:
            self._add_reference(reference)

    def _add_achievement(self, achievement: Achievement) -> None:
        self._add_text(achievement.description)
        if achievement.measurable_result:
            self._add_text(achievement.measurable_result)
        for reference in achievement.references:
            self._add_reference(reference)

    def _add_reference(self, reference: EvidenceReference) -> None:
        self._references.add((_normalize_key(reference.source_section), _normalize_key(reference.source_excerpt)))
        self._add_text(reference.source_excerpt)

    def _add_text(self, value: str | None) -> None:
        if value:
            self._statements.add(_normalize_key(value))


def _requirement_matches(match: SemanticRequirementMatch, requirement: JobRequirement) -> bool:
    candidates = [_normalize_key(match.requirement_name), _normalize_key(match.normalized_requirement)]
    expected = {_normalize_key(requirement.name), _normalize_key(requirement.normalized_name)}
    expected.update(_normalize_key(keyword) for keyword in requirement.exact_keywords)
    return any(_phrase_or_tokens_found(candidate, expected) for candidate in candidates if candidate)


def _find_match(matches, requirement_name: str):
    key = _normalize_key(requirement_name)
    for match in matches:
        if _phrase_or_tokens_found(key, {_normalize_key(match.requirement_name), _normalize_key(match.normalized_requirement)}):
            return match
    return None


def _is_finite_between(value: float, minimum: float, maximum: float) -> bool:
    return math.isfinite(value) and minimum <= value <= maximum


def _titles_correspond(expected: str, actual: str) -> bool:
    expected_tokens = {token for token in _normalize_key(expected).split() if len(token) > 2}
    actual_tokens = {token for token in _normalize_key(actual).split() if len(token) > 2}
    if not expected_tokens or not actual_tokens:
        return False
    overlap = expected_tokens & actual_tokens
    return bool(overlap) and len(overlap) / min(len(expected_tokens), len(actual_tokens)) >= 0.4


def _company_corresponds(expected: str, actual: str | None) -> bool:
    if not actual:
        return False
    return _normalize_key(expected) == _normalize_key(actual)


def _phrase_or_tokens_found(candidate: str, haystack: set[str]) -> bool:
    if not candidate:
        return False
    if candidate in haystack:
        return True
    if any(candidate in item or item in candidate for item in haystack if item):
        return True
    tokens = [token for token in candidate.split() if len(token) > 2]
    if not tokens:
        return False
    haystack_tokens = set()
    for item in haystack:
        haystack_tokens.update(item.split())
    matches = sum(1 for token in tokens if token in haystack_tokens)
    return matches >= max(1, min(2, len(tokens))) and matches / len(tokens) >= 0.5


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    ascii_text = ascii_text.casefold()
    ascii_text = re.sub(r"[^\w+#.]+", " ", ascii_text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _add_error(findings: list[CompatibilityAuditFinding], path: str, message: str) -> None:
    findings.append(CompatibilityAuditFinding(severity="error", path=path, message=message))


def _add_warning(findings: list[CompatibilityAuditFinding], path: str, message: str) -> None:
    findings.append(CompatibilityAuditFinding(severity="warning", path=path, message=message))
