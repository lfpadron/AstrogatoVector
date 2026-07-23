"""Deterministic compatibility scoring engine."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from schemas.compatibility_analysis_models import CompatibilitySemanticEvaluation, SemanticRequirementMatch
from schemas.compatibility_models import (
    COMPATIBILITY_DIMENSION_LABELS_ES,
    COMPATIBILITY_DIMENSION_WEIGHTS,
    COMPATIBILITY_DISCLAIMER_EN,
    COMPATIBILITY_DISCLAIMER_ES,
    COMPATIBILITY_METHODOLOGY_VERSION,
    CompatibilityDimension,
    CompatibilityPenalty,
    CompatibilityReport,
    JobCompatibility,
    RequirementMatch,
    compatibility_band_for_score,
)
from schemas.enums import (
    CompatibilityDimensionName,
    EvidenceStatus,
    OutputLanguage,
    PriorityLevel,
    RequirementCoverage,
    SeniorityLevel,
    SkillCategory,
)
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis, TargetMarketAnalysis

COVERAGE_POINTS = {
    RequirementCoverage.FULL.value: 1.00,
    RequirementCoverage.PARTIAL.value: 0.65,
    RequirementCoverage.INDIRECT.value: 0.35,
    RequirementCoverage.MISSING.value: 0.00,
    RequirementCoverage.CONFLICT.value: 0.00,
    RequirementCoverage.NOT_APPLICABLE.value: None,
}
EVIDENCE_STATUS_FACTORS = {
    EvidenceStatus.SUPPORTED.value: 1.00,
    EvidenceStatus.INFERRED.value: 0.75,
    EvidenceStatus.MISSING.value: 0.00,
    EvidenceStatus.CONFLICT.value: 0.00,
}
REQUIREMENT_PRIORITY_WEIGHTS = {
    PriorityLevel.CRITICAL.value: 1.50,
    PriorityLevel.HIGH.value: 1.25,
    PriorityLevel.MEDIUM.value: 1.00,
    PriorityLevel.LOW.value: 0.75,
}
REQUIRED_REQUIREMENT_MULTIPLIER = 1.20
PREFERRED_REQUIREMENT_MULTIPLIER = 1.00
CRITICAL_REQUIRED_MISSING_PENALTY = 5.0
MAX_CRITICAL_MISSING_PENALTY = 20.0
SENIORITY_GAP_PENALTY = 5.0
MANDATORY_LANGUAGE_MISSING_PENALTY = 5.0
SCORING_CONSTANTS_VERSION = "1.0"

SENIORITY_ORDER = {
    SeniorityLevel.ENTRY.value: 0,
    SeniorityLevel.MID.value: 1,
    SeniorityLevel.SENIOR.value: 2,
    SeniorityLevel.LEAD.value: 3,
    SeniorityLevel.MANAGER.value: 4,
    SeniorityLevel.DIRECTOR.value: 5,
    SeniorityLevel.EXECUTIVE.value: 6,
}
LANGUAGE_PATTERN = re.compile(r"\b(english|ingles|inglés|idioma|language|bilingual|bilingue|bilingüe)\b", re.I)
CERTIFICATION_PATTERN = re.compile(r"\b(certification|certificacion|certificación|certificado|pmp|scrum master)\b", re.I)
EDUCATION_PATTERN = re.compile(r"\b(education|educacion|educación|degree|bachelor|licenciatura|maestria|maestría|master)\b", re.I)
TOOL_PATTERN = re.compile(
    r"\b(jira|aws|kubernetes|azure|gcp|sap|docker|excel|sql|python|power bi|tableau|salesforce|cloud)\b",
    re.I,
)
LEADERSHIP_PATTERN = re.compile(
    r"\b(leadership|liderazgo|management|gestion|gestión|stakeholder|equipo|team|people|comunicacion|comunicación)\b",
    re.I,
)
EXPERIENCE_PATTERN = re.compile(
    r"\b(experience|experiencia|responsabilidad|responsibility|project management|program management|"
    r"gestion de proyectos|gestión de proyectos|riesgo|risk|delivery|implementacion|implementación)\b",
    re.I,
)
INDUSTRY_PATTERN = re.compile(r"\b(industry|industria|sector|domain|dominio|fintech|salud|retail|tecnologia|tecnología)\b", re.I)


class CompatibilityScoringService:
    """Calculate CompatibilityReport without calling OpenAI."""

    def calculate_report(
        self,
        semantic_evaluation: CompatibilitySemanticEvaluation,
        market_analysis: TargetMarketAnalysis,
        candidate_profile: CandidateProfessionalProfile | None = None,
        output_language: OutputLanguage | str = OutputLanguage.ES,
    ) -> CompatibilityReport:
        """Build a deterministic score report from semantic coverage."""
        jobs_by_index = {job.job_index: job for job in market_analysis.job_analyses}
        compatibilities = [
            self._calculate_job(
                job_evaluation,
                jobs_by_index[job_evaluation.job_index],
                candidate_profile,
            )
            for job_evaluation in sorted(semantic_evaluation.job_evaluations, key=lambda item: item.job_index)
        ]
        average = _round_score(sum(job.compatibility_score for job in compatibilities) / len(compatibilities))
        highest = max(compatibilities, key=lambda job: (job.compatibility_score, -job.job_index)).job_index
        return CompatibilityReport(
            job_compatibilities=compatibilities,
            highest_compatibility_job_index=highest,
            average_compatibility_score=average,
            common_strengths=_common_items([job.strengths for job in compatibilities], limit=5),
            common_gaps=_common_items([job.critical_gaps + job.other_gaps for job in compatibilities], limit=5),
            strategic_recommendations=_strategic_recommendations(compatibilities),
            methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
            disclaimer=_disclaimer_for_language(output_language),
        )

    def _calculate_job(
        self,
        job_evaluation,
        job_analysis: JobAnalysis,
        candidate_profile: CandidateProfessionalProfile | None,
    ) -> JobCompatibility:
        requirement_matches = [
            _final_requirement_match(match)
            for match in job_evaluation.requirement_matches
        ]
        evaluable_matches = [
            match
            for match in requirement_matches
            if match.coverage != RequirementCoverage.NOT_APPLICABLE.value
        ]
        if not evaluable_matches:
            raise ValueError("compatibility scoring requires at least one evaluable requirement per job")

        dimensions = _calculate_dimensions(evaluable_matches)
        score_before = _round_score(sum((dimension.score or 0.0) * dimension.effective_weight for dimension in dimensions))
        penalties = _calculate_penalties(evaluable_matches, job_analysis, candidate_profile)
        total_penalty = _round_score(sum(penalty.points for penalty in penalties))
        final_score = _round_score(max(0.0, min(100.0, score_before - total_penalty)))
        confidence = _weighted_confidence(evaluable_matches)
        covered_required, total_required, covered_preferred, total_preferred = _coverage_counts(evaluable_matches)

        critical_gaps = _critical_gaps(evaluable_matches, penalties)
        other_gaps = _other_gaps(evaluable_matches, critical_gaps)
        recommendations = _recommendations(evaluable_matches, job_evaluation.development_opportunities, critical_gaps)
        strengths = _strengths(evaluable_matches, job_evaluation.strengths)

        return JobCompatibility(
            job_index=job_evaluation.job_index,
            job_title=job_evaluation.job_title or job_analysis.title,
            company=job_evaluation.company if job_evaluation.company is not None else job_analysis.company,
            compatibility_score=final_score,
            compatibility_band=compatibility_band_for_score(final_score),
            score_before_penalties=score_before,
            total_penalty=total_penalty,
            penalties=penalties,
            dimensions=dimensions,
            requirement_matches=requirement_matches,
            strengths=strengths,
            critical_gaps=critical_gaps,
            other_gaps=other_gaps,
            risks=_unique_preserving_order(job_evaluation.risks)[:5],
            recommendations=recommendations,
            confidence=confidence,
            summary=job_evaluation.summary,
            covered_required_count=covered_required,
            total_required_count=total_required,
            covered_preferred_count=covered_preferred,
            total_preferred_count=total_preferred,
        )


def _final_requirement_match(match: SemanticRequirementMatch) -> RequirementMatch:
    coverage = _enum_value(match.coverage)
    evidence_status = _enum_value(match.candidate_evidence_status)
    coverage_value = COVERAGE_POINTS.get(coverage)
    evidence_factor = EVIDENCE_STATUS_FACTORS.get(evidence_status, 0.0)
    requirement_score = 0.0 if coverage_value is None else coverage_value * evidence_factor
    weight = _requirement_weight(match)
    dimension_id = _dimension_for_match(match.category, match.requirement_name, match.normalized_requirement)
    return RequirementMatch(
        requirement_name=match.requirement_name,
        normalized_requirement=match.normalized_requirement,
        category=match.category,
        dimension_id=dimension_id,
        required=match.required,
        priority=match.priority,
        coverage=match.coverage,
        evidence_status=match.candidate_evidence_status,
        coverage_points=0.0 if coverage_value is None else coverage_value,
        evidence_factor=evidence_factor,
        weighted_match_value=requirement_score * weight,
        candidate_evidence=match.candidate_evidence,
        matched_candidate_items=match.matched_candidate_items,
        missing_elements=match.missing_elements,
        explanation=match.explanation,
        recommendation=_recommendation_for_match(match),
        confidence=match.confidence,
    )


def _calculate_dimensions(matches: list[RequirementMatch]) -> list[CompatibilityDimension]:
    groups: dict[str, list[RequirementMatch]] = defaultdict(list)
    for match in matches:
        groups[_enum_value(match.dimension_id)].append(match)

    evaluated_weight_sum = sum(
        COMPATIBILITY_DIMENSION_WEIGHTS[dimension_id]
        for dimension_id, items in groups.items()
        if items
    )
    if evaluated_weight_sum <= 0:
        raise ValueError("at least one compatibility dimension must be evaluated")

    dimensions: list[CompatibilityDimension] = []
    for dimension_id, original_weight in COMPATIBILITY_DIMENSION_WEIGHTS.items():
        items = groups.get(dimension_id, [])
        evaluated = bool(items)
        score = _dimension_score(items) if evaluated else None
        effective_weight = _round_weight(original_weight / evaluated_weight_sum) if evaluated else 0.0
        dimensions.append(
            CompatibilityDimension(
                dimension_id=dimension_id,
                display_name=COMPATIBILITY_DIMENSION_LABELS_ES[dimension_id],
                original_weight=original_weight,
                effective_weight=effective_weight,
                evaluated=evaluated,
                score=score,
                total_requirements=len(items),
                full_matches=_count_coverage(items, RequirementCoverage.FULL),
                partial_matches=_count_coverage(items, RequirementCoverage.PARTIAL),
                indirect_matches=_count_coverage(items, RequirementCoverage.INDIRECT),
                missing_matches=_count_coverage(items, RequirementCoverage.MISSING),
                conflict_matches=_count_coverage(items, RequirementCoverage.CONFLICT),
                explanation=_dimension_explanation(dimension_id, score, len(items)),
            )
        )
    return _normalize_effective_weights(dimensions)


def _dimension_score(matches: list[RequirementMatch]) -> float:
    denominator = sum(_final_requirement_weight(match) for match in matches)
    if denominator <= 0:
        return 0.0
    numerator = sum(match.weighted_match_value for match in matches)
    return _round_score(numerator / denominator * 100)


def _calculate_penalties(
    matches: list[RequirementMatch],
    job_analysis: JobAnalysis,
    candidate_profile: CandidateProfessionalProfile | None,
) -> list[CompatibilityPenalty]:
    penalties: list[CompatibilityPenalty] = []
    critical_penalized_requirements: set[str] = set()
    critical_missing = [
        match
        for match in matches
        if match.required
        and match.priority == PriorityLevel.CRITICAL.value
        and match.coverage in {RequirementCoverage.MISSING.value, RequirementCoverage.CONFLICT.value}
    ]
    for match in critical_missing[: int(MAX_CRITICAL_MISSING_PENALTY / CRITICAL_REQUIRED_MISSING_PENALTY)]:
        critical_penalized_requirements.add(_normalize_key(match.normalized_requirement))
        penalties.append(
            CompatibilityPenalty(
                penalty_type="critical_required_missing",
                points=CRITICAL_REQUIRED_MISSING_PENALTY,
                reason=f"Requisito crítico obligatorio no respaldado: {match.requirement_name}.",
                related_requirement=match.requirement_name,
            )
        )

    seniority_penalty = _seniority_penalty(job_analysis, candidate_profile)
    if seniority_penalty is not None:
        penalties.append(seniority_penalty)

    language_match = next(
        (
            match
            for match in matches
            if match.required
            and _is_language_requirement(match)
            and match.coverage in {RequirementCoverage.MISSING.value, RequirementCoverage.CONFLICT.value}
            and _normalize_key(match.normalized_requirement) not in critical_penalized_requirements
        ),
        None,
    )
    if language_match is not None:
        penalties.append(
            CompatibilityPenalty(
                penalty_type="mandatory_language_missing",
                points=MANDATORY_LANGUAGE_MISSING_PENALTY,
                reason=f"Idioma obligatorio ausente o no respaldado: {language_match.requirement_name}.",
                related_requirement=language_match.requirement_name,
            )
        )
    return penalties


def _seniority_penalty(
    job_analysis: JobAnalysis,
    candidate_profile: CandidateProfessionalProfile | None,
) -> CompatibilityPenalty | None:
    if candidate_profile is None:
        return None
    job_seniority = _enum_value(job_analysis.inferred_seniority)
    candidate_seniority = _enum_value(candidate_profile.seniority)
    if job_seniority == SeniorityLevel.UNSPECIFIED.value or candidate_seniority == SeniorityLevel.UNSPECIFIED.value:
        return None
    job_rank = SENIORITY_ORDER.get(job_seniority)
    candidate_rank = SENIORITY_ORDER.get(candidate_seniority)
    if job_rank is None or candidate_rank is None or job_rank - candidate_rank < 2:
        return None
    return CompatibilityPenalty(
        penalty_type="seniority_gap",
        points=SENIORITY_GAP_PENALTY,
        reason=(
            "La vacante presenta un seniority significativamente superior al seniority respaldado "
            "en el perfil profesional."
        ),
        related_requirement="seniority",
    )


def _dimension_for_match(category: SkillCategory | str, name: str, normalized: str) -> str:
    text = _normalize_for_match(f"{name} {normalized}")
    if LANGUAGE_PATTERN.search(text) or CERTIFICATION_PATTERN.search(text) or EDUCATION_PATTERN.search(text):
        return CompatibilityDimensionName.EDUCATION_CERTIFICATIONS_LANGUAGES.value
    if TOOL_PATTERN.search(text):
        return CompatibilityDimensionName.TOOLS_TECHNOLOGIES.value
    if INDUSTRY_PATTERN.search(text):
        return CompatibilityDimensionName.INDUSTRY_BUSINESS.value
    if "stakeholder" in text:
        return CompatibilityDimensionName.LEADERSHIP_MANAGEMENT.value
    if EXPERIENCE_PATTERN.search(text):
        return CompatibilityDimensionName.EXPERIENCE_RESPONSIBILITIES.value
    if LEADERSHIP_PATTERN.search(text):
        return CompatibilityDimensionName.LEADERSHIP_MANAGEMENT.value

    category_value = _enum_value(category)
    category_map = {
        SkillCategory.TECHNICAL.value: CompatibilityDimensionName.SKILLS_KNOWLEDGE.value,
        SkillCategory.BUSINESS.value: CompatibilityDimensionName.SKILLS_KNOWLEDGE.value,
        SkillCategory.STRATEGY.value: CompatibilityDimensionName.SKILLS_KNOWLEDGE.value,
        SkillCategory.TOOL.value: CompatibilityDimensionName.TOOLS_TECHNOLOGIES.value,
        SkillCategory.LEADERSHIP.value: CompatibilityDimensionName.LEADERSHIP_MANAGEMENT.value,
        SkillCategory.COMMUNICATION.value: CompatibilityDimensionName.LEADERSHIP_MANAGEMENT.value,
        SkillCategory.INDUSTRY.value: CompatibilityDimensionName.INDUSTRY_BUSINESS.value,
        SkillCategory.LANGUAGE.value: CompatibilityDimensionName.EDUCATION_CERTIFICATIONS_LANGUAGES.value,
    }
    return category_map.get(category_value, CompatibilityDimensionName.SKILLS_KNOWLEDGE.value)


def _requirement_weight(match: SemanticRequirementMatch) -> float:
    priority = _enum_value(match.priority)
    base = REQUIREMENT_PRIORITY_WEIGHTS.get(priority, REQUIREMENT_PRIORITY_WEIGHTS[PriorityLevel.MEDIUM.value])
    return base * (REQUIRED_REQUIREMENT_MULTIPLIER if match.required else PREFERRED_REQUIREMENT_MULTIPLIER)


def _final_requirement_weight(match: RequirementMatch) -> float:
    priority = _enum_value(match.priority)
    base = REQUIREMENT_PRIORITY_WEIGHTS.get(priority, REQUIREMENT_PRIORITY_WEIGHTS[PriorityLevel.MEDIUM.value])
    return base * (REQUIRED_REQUIREMENT_MULTIPLIER if match.required else PREFERRED_REQUIREMENT_MULTIPLIER)


def _weighted_confidence(matches: list[RequirementMatch]) -> float:
    denominator = sum(_final_requirement_weight(match) for match in matches)
    if denominator <= 0:
        return 0.0
    numerator = sum(match.confidence * _final_requirement_weight(match) for match in matches)
    return _round_confidence(numerator / denominator)


def _coverage_counts(matches: list[RequirementMatch]) -> tuple[int, int, int, int]:
    required = [match for match in matches if match.required]
    preferred = [match for match in matches if not match.required]
    covered_required = sum(1 for match in required if match.coverage == RequirementCoverage.FULL.value)
    covered_preferred = sum(1 for match in preferred if match.coverage == RequirementCoverage.FULL.value)
    return covered_required, len(required), covered_preferred, len(preferred)


def _critical_gaps(matches: list[RequirementMatch], penalties: list[CompatibilityPenalty]) -> list[str]:
    gaps = [
        _gap_text(match)
        for match in matches
        if match.required
        and match.priority in {PriorityLevel.CRITICAL.value, PriorityLevel.HIGH.value}
        and match.coverage in {RequirementCoverage.MISSING.value, RequirementCoverage.CONFLICT.value}
    ]
    for penalty in penalties:
        if penalty.penalty_type in {"seniority_gap", "mandatory_language_missing"}:
            gaps.append(penalty.reason)
    return _unique_preserving_order(gaps)[:8]


def _other_gaps(matches: list[RequirementMatch], critical_gaps: list[str]) -> list[str]:
    critical_keys = {_normalize_key(gap) for gap in critical_gaps}
    gaps = []
    for match in matches:
        if match.coverage not in {
            RequirementCoverage.PARTIAL.value,
            RequirementCoverage.INDIRECT.value,
            RequirementCoverage.MISSING.value,
            RequirementCoverage.CONFLICT.value,
        }:
            continue
        text = _gap_text(match)
        if _normalize_key(text) not in critical_keys:
            gaps.append(text)
    return _unique_preserving_order(gaps)[:10]


def _recommendations(
    matches: list[RequirementMatch],
    development_opportunities: list[str],
    critical_gaps: list[str],
) -> list[str]:
    recommendations = [match.recommendation for match in matches if match.recommendation]
    recommendations.extend(development_opportunities)
    if critical_gaps:
        recommendations.append("Revisar las brechas críticas antes de decidir si conviene postular.")
    return _unique_preserving_order([item for item in recommendations if item])[:10]


def _strengths(matches: list[RequirementMatch], semantic_strengths: list[str]) -> list[str]:
    strengths = list(semantic_strengths)
    for match in matches:
        if (
            match.coverage == RequirementCoverage.FULL.value
            and match.evidence_status == EvidenceStatus.SUPPORTED.value
            and match.priority in {PriorityLevel.CRITICAL.value, PriorityLevel.HIGH.value}
        ):
            strengths.append(match.requirement_name)
    return _unique_preserving_order(strengths)[:5]


def _recommendation_for_match(match: SemanticRequirementMatch) -> str | None:
    coverage = _enum_value(match.coverage)
    name = match.requirement_name
    if coverage == RequirementCoverage.FULL.value:
        return f"Preparar un ejemplo de entrevista que demuestre {name} con evidencia concreta."
    if coverage == RequirementCoverage.PARTIAL.value:
        return f"Destacar la evidencia existente de {name} y aclarar honestamente el alcance que falta."
    if coverage == RequirementCoverage.INDIRECT.value:
        return f"Explicar {name} como experiencia transferible, sin presentarla como dominio directo."
    if coverage == RequirementCoverage.MISSING.value:
        if _is_language_text(name):
            return f"Desarrollar o certificar el idioma solicitado antes de presentarlo como capacidad."
        if CERTIFICATION_PATTERN.search(_normalize_for_match(name)):
            return f"Considerar la certificación solicitada si es relevante para la trayectoria objetivo."
        if TOOL_PATTERN.search(_normalize_for_match(name)):
            return f"Adquirir práctica verificable en {name} antes de incorporarlo al perfil."
        return f"No declarar {name} como experiencia si no existe evidencia profesional."
    if coverage == RequirementCoverage.CONFLICT.value:
        return f"Aclarar el conflicto relacionado con {name} antes de usarlo en una postulación."
    return None


def _dimension_explanation(dimension_id: str, score: float | None, count: int) -> str:
    label = COMPATIBILITY_DIMENSION_LABELS_ES[dimension_id]
    if score is None:
        return f"{label} no fue solicitada por esta vacante y su peso se redistribuyó."
    return f"{label} se calculó con {count} requisito(s) evaluable(s)."


def _normalize_effective_weights(dimensions: list[CompatibilityDimension]) -> list[CompatibilityDimension]:
    evaluated = [dimension for dimension in dimensions if dimension.evaluated]
    if not evaluated:
        return dimensions
    total = sum(dimension.effective_weight for dimension in evaluated)
    delta = _round_weight(1.0 - total)
    if abs(delta) <= 0.000001:
        return dimensions
    last_id = evaluated[-1].dimension_id
    normalized = []
    for dimension in dimensions:
        if dimension.dimension_id == last_id:
            normalized.append(
                dimension.model_copy(update={"effective_weight": _round_weight(dimension.effective_weight + delta)})
            )
        else:
            normalized.append(dimension)
    return normalized


def _count_coverage(matches: list[RequirementMatch], coverage: RequirementCoverage) -> int:
    return sum(1 for match in matches if match.coverage == coverage.value)


def _is_language_requirement(match: RequirementMatch) -> bool:
    return _is_language_text(f"{match.requirement_name} {match.normalized_requirement}")


def _is_language_text(text: str) -> bool:
    return bool(LANGUAGE_PATTERN.search(_normalize_for_match(text)))


def _gap_text(match: RequirementMatch) -> str:
    missing = "; ".join(match.missing_elements[:2])
    suffix = f" Falta: {missing}." if missing else ""
    return f"{match.requirement_name}: {match.explanation}{suffix}"


def _common_items(groups: list[list[str]], *, limit: int) -> list[str]:
    if not groups:
        return []
    counter: Counter[str] = Counter()
    original_by_key: dict[str, str] = {}
    for group in groups:
        seen_in_group = set()
        for item in group:
            key = _normalize_key(item)
            if not key or key in seen_in_group:
                continue
            seen_in_group.add(key)
            original_by_key.setdefault(key, item)
            counter[key] += 1
    common = [key for key, count in counter.most_common() if count >= 2]
    return [original_by_key[key] for key in common[:limit]]


def _strategic_recommendations(jobs: list[JobCompatibility]) -> list[str]:
    recommendations = []
    if jobs:
        highest = max(jobs, key=lambda job: (job.compatibility_score, -job.job_index))
        recommendations.append(
            f"La vacante {highest.job_index} presenta la mayor alineación demostrable entre las ofertas analizadas."
        )
    common_gaps = _common_items([job.critical_gaps + job.other_gaps for job in jobs], limit=3)
    for gap in common_gaps:
        recommendations.append(f"Atender brecha recurrente: {gap}")
    recommendations.append(
        "Considerar también interés personal, salario, ubicación, cultura, condiciones y crecimiento antes de decidir."
    )
    return _unique_preserving_order(recommendations)[:6]


def _disclaimer_for_language(output_language: OutputLanguage | str) -> str:
    return COMPATIBILITY_DISCLAIMER_EN if _enum_value(output_language) == OutputLanguage.EN.value else COMPATIBILITY_DISCLAIMER_ES


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _round_score(value: float) -> float:
    return round(value + 0.0000000001, 1)


def _round_weight(value: float) -> float:
    return round(value, 8)


def _round_confidence(value: float) -> float:
    return round(value + 0.0000000001, 2)


def _normalize_key(value: str) -> str:
    return _normalize_for_match(value)


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    ascii_text = ascii_text.casefold()
    ascii_text = re.sub(r"[^\w+#.]+", " ", ascii_text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
