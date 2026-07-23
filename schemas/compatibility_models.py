"""Compatibility score models and mathematical validators."""

from __future__ import annotations

import math

from pydantic import Field, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import (
    CompatibilityBand,
    CompatibilityDimensionName,
    EvidenceStatus,
    PriorityLevel,
    RequirementCoverage,
    SkillCategory,
)
from schemas.evidence_models import EvidenceItem

SCORE_TOLERANCE = 0.11
WEIGHT_TOLERANCE = 0.000001
COMPATIBILITY_METHODOLOGY_VERSION = "1.0"
COMPATIBILITY_DISCLAIMER_ES = (
    "Este score expresa alineación entre la evidencia profesional disponible y los requisitos identificados "
    "en las vacantes seleccionadas. No representa una probabilidad de contratación ni garantiza resultados "
    "en un proceso de selección."
)
COMPATIBILITY_DISCLAIMER_EN = (
    "This score expresses alignment between the available professional evidence and the requirements identified "
    "in the selected job postings. It does not represent a hiring probability and does not guarantee outcomes "
    "in a selection process."
)
COMPATIBILITY_DIMENSION_WEIGHTS = {
    CompatibilityDimensionName.EXPERIENCE_RESPONSIBILITIES.value: 0.30,
    CompatibilityDimensionName.SKILLS_KNOWLEDGE.value: 0.25,
    CompatibilityDimensionName.TOOLS_TECHNOLOGIES.value: 0.15,
    CompatibilityDimensionName.LEADERSHIP_MANAGEMENT.value: 0.12,
    CompatibilityDimensionName.INDUSTRY_BUSINESS.value: 0.10,
    CompatibilityDimensionName.EDUCATION_CERTIFICATIONS_LANGUAGES.value: 0.08,
}
COMPATIBILITY_DIMENSION_LABELS_ES = {
    CompatibilityDimensionName.EXPERIENCE_RESPONSIBILITIES.value: "Experiencia y responsabilidades",
    CompatibilityDimensionName.SKILLS_KNOWLEDGE.value: "Skills y conocimientos",
    CompatibilityDimensionName.TOOLS_TECHNOLOGIES.value: "Herramientas y tecnologías",
    CompatibilityDimensionName.LEADERSHIP_MANAGEMENT.value: "Liderazgo y gestión",
    CompatibilityDimensionName.INDUSTRY_BUSINESS.value: "Industria y contexto de negocio",
    CompatibilityDimensionName.EDUCATION_CERTIFICATIONS_LANGUAGES.value: "Educación, certificaciones e idiomas",
}
COMPATIBILITY_BANDS = {
    CompatibilityBand.VERY_HIGH.value: (85.0, 100.0),
    CompatibilityBand.HIGH.value: (70.0, 84.9),
    CompatibilityBand.MODERATE.value: (55.0, 69.9),
    CompatibilityBand.LOW.value: (40.0, 54.9),
    CompatibilityBand.VERY_LOW.value: (0.0, 39.9),
}
COMPATIBILITY_BAND_LABELS_ES = {
    CompatibilityBand.VERY_HIGH.value: "Muy alta",
    CompatibilityBand.HIGH.value: "Alta",
    CompatibilityBand.MODERATE.value: "Moderada",
    CompatibilityBand.LOW.value: "Baja",
    CompatibilityBand.VERY_LOW.value: "Muy baja",
}
COMPATIBILITY_BAND_LABELS_EN = {
    CompatibilityBand.VERY_HIGH.value: "Very high",
    CompatibilityBand.HIGH.value: "High",
    CompatibilityBand.MODERATE.value: "Moderate",
    CompatibilityBand.LOW.value: "Low",
    CompatibilityBand.VERY_LOW.value: "Very low",
}
ALLOWED_PENALTY_TYPES = {
    "critical_required_missing",
    "seniority_gap",
    "mandatory_language_missing",
}


class CompatibilityDimension(StrictBaseModel):
    """One weighted score dimension for a target job."""

    dimension_id: CompatibilityDimensionName
    display_name: str = Field(min_length=1, max_length=160)
    original_weight: float = Field(ge=0.0, le=1.0)
    effective_weight: float = Field(ge=0.0, le=1.0)
    evaluated: bool
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    total_requirements: int = Field(ge=0)
    full_matches: int = Field(ge=0)
    partial_matches: int = Field(ge=0)
    indirect_matches: int = Field(ge=0)
    missing_matches: int = Field(ge=0)
    conflict_matches: int = Field(ge=0)
    explanation: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_dimension(self) -> CompatibilityDimension:
        dimension_id = _enum_value(self.dimension_id)
        if dimension_id not in COMPATIBILITY_DIMENSION_WEIGHTS:
            raise ValueError("dimension_id must be one of the six compatibility dimensions")
        expected_weight = COMPATIBILITY_DIMENSION_WEIGHTS[dimension_id]
        if abs(self.original_weight - expected_weight) > WEIGHT_TOLERANCE:
            raise ValueError(f"{dimension_id} must have original_weight {expected_weight}")
        if self.evaluated and self.score is None:
            raise ValueError("evaluated dimensions must include score")
        if not self.evaluated:
            if self.score is not None:
                raise ValueError("non-evaluated dimensions must have score=None")
            if self.effective_weight != 0:
                raise ValueError("non-evaluated dimensions must have effective_weight=0")
        counted = (
            self.full_matches
            + self.partial_matches
            + self.indirect_matches
            + self.missing_matches
            + self.conflict_matches
        )
        if counted > self.total_requirements:
            raise ValueError("dimension match counts cannot exceed total_requirements")
        _validate_finite_optional(self.score, "score")
        _validate_finite(self.original_weight, "original_weight")
        _validate_finite(self.effective_weight, "effective_weight")
        return self


class RequirementMatch(StrictBaseModel):
    """Candidate match against a specific requirement."""

    requirement_name: str = Field(min_length=1, max_length=300)
    normalized_requirement: str = Field(min_length=1, max_length=300)
    category: SkillCategory
    dimension_id: CompatibilityDimensionName
    required: bool
    priority: PriorityLevel
    coverage: RequirementCoverage
    evidence_status: EvidenceStatus
    coverage_points: float = Field(ge=0.0, le=1.0)
    evidence_factor: float = Field(ge=0.0, le=1.0)
    weighted_match_value: float = Field(ge=0.0)
    candidate_evidence: list[EvidenceItem] = Field(default_factory=list)
    matched_candidate_items: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1, max_length=1200)
    recommendation: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_requirement_match(self) -> RequirementMatch:
        dimension_id = _enum_value(self.dimension_id)
        if dimension_id not in COMPATIBILITY_DIMENSION_WEIGHTS:
            raise ValueError("dimension_id must be one of the six compatibility dimensions")
        if self.coverage == RequirementCoverage.FULL.value and self.evidence_status != EvidenceStatus.SUPPORTED.value:
            raise ValueError("full coverage requires SUPPORTED evidence")
        if self.coverage == RequirementCoverage.MISSING.value and self.candidate_evidence:
            raise ValueError("missing coverage cannot include candidate evidence")
        if self.coverage == RequirementCoverage.CONFLICT.value and not self.explanation:
            raise ValueError("conflict coverage requires explanation")
        _validate_finite(self.coverage_points, "coverage_points")
        _validate_finite(self.evidence_factor, "evidence_factor")
        _validate_finite(self.weighted_match_value, "weighted_match_value")
        _validate_finite(self.confidence, "confidence")
        return self


class CompatibilityPenalty(StrictBaseModel):
    """Traceable score adjustment applied by the deterministic engine."""

    penalty_type: str = Field(min_length=1, max_length=80)
    points: float = Field(ge=0.0, le=20.0)
    reason: str = Field(min_length=1, max_length=1000)
    related_requirement: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_penalty(self) -> CompatibilityPenalty:
        if self.penalty_type not in ALLOWED_PENALTY_TYPES:
            raise ValueError("penalty_type is not allowed")
        _validate_finite(self.points, "points")
        return self


class JobCompatibility(StrictBaseModel):
    """Compatibility report for one target job."""

    job_index: int = Field(ge=1, le=6)
    job_title: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    compatibility_score: float = Field(ge=0.0, le=100.0)
    compatibility_band: CompatibilityBand
    score_before_penalties: float = Field(ge=0.0, le=100.0)
    total_penalty: float = Field(ge=0.0, le=30.0)
    penalties: list[CompatibilityPenalty] = Field(default_factory=list)
    dimensions: list[CompatibilityDimension] = Field(min_length=6, max_length=6)
    requirement_matches: list[RequirementMatch] = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    other_gaps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=1600)
    covered_required_count: int = Field(default=0, ge=0)
    total_required_count: int = Field(default=0, ge=0)
    covered_preferred_count: int = Field(default=0, ge=0)
    total_preferred_count: int = Field(default=0, ge=0)

    @property
    def total_score(self) -> float:
        """Backward-compatible alias for older callers."""
        return self.compatibility_score

    @model_validator(mode="after")
    def validate_job_compatibility(self) -> JobCompatibility:
        dimension_ids = [_enum_value(dimension.dimension_id) for dimension in self.dimensions]
        if len(dimension_ids) != len(set(dimension_ids)):
            raise ValueError("compatibility dimensions must be unique")
        if set(dimension_ids) != set(COMPATIBILITY_DIMENSION_WEIGHTS):
            raise ValueError("compatibility dimensions must be exactly the six required dimensions")

        original_weight_sum = sum(dimension.original_weight for dimension in self.dimensions)
        if abs(original_weight_sum - 1.0) > WEIGHT_TOLERANCE:
            raise ValueError("compatibility dimension original weights must sum to 1.0")

        evaluated_dimensions = [dimension for dimension in self.dimensions if dimension.evaluated]
        effective_weight_sum = sum(dimension.effective_weight for dimension in evaluated_dimensions)
        if evaluated_dimensions and abs(effective_weight_sum - 1.0) > SCORE_TOLERANCE / 100:
            raise ValueError("effective weights for evaluated dimensions must sum to 1.0")

        expected_before = sum((dimension.score or 0.0) * dimension.effective_weight for dimension in self.dimensions)
        if abs(self.score_before_penalties - _round_score(expected_before)) > SCORE_TOLERANCE:
            raise ValueError("score_before_penalties must equal weighted dimension scores")

        penalty_sum = sum(penalty.points for penalty in self.penalties)
        if abs(self.total_penalty - _round_score(penalty_sum)) > SCORE_TOLERANCE:
            raise ValueError("total_penalty must equal the sum of penalties")

        expected_final = _round_score(max(0.0, min(100.0, self.score_before_penalties - self.total_penalty)))
        if abs(self.compatibility_score - expected_final) > SCORE_TOLERANCE:
            raise ValueError("compatibility_score must equal score_before_penalties minus penalties")

        if _enum_value(self.compatibility_band) != compatibility_band_for_score(self.compatibility_score):
            raise ValueError("compatibility_band must correspond to compatibility_score")

        if self.covered_required_count > self.total_required_count:
            raise ValueError("covered_required_count cannot exceed total_required_count")
        if self.covered_preferred_count > self.total_preferred_count:
            raise ValueError("covered_preferred_count cannot exceed total_preferred_count")

        _validate_finite(self.compatibility_score, "compatibility_score")
        _validate_finite(self.score_before_penalties, "score_before_penalties")
        _validate_finite(self.total_penalty, "total_penalty")
        _validate_finite(self.confidence, "confidence")
        return self


class CompatibilityReport(StrictBaseModel):
    """Consolidated compatibility report across target jobs."""

    job_compatibilities: list[JobCompatibility] = Field(min_length=2, max_length=6)
    highest_compatibility_job_index: int | None = Field(default=None, ge=1, le=6)
    average_compatibility_score: float = Field(ge=0.0, le=100.0)
    common_strengths: list[str] = Field(default_factory=list)
    common_gaps: list[str] = Field(default_factory=list)
    strategic_recommendations: list[str] = Field(default_factory=list)
    methodology_version: str = Field(min_length=1, max_length=40)
    disclaimer: str = Field(min_length=20, max_length=1200)

    @property
    def jobs(self) -> list[JobCompatibility]:
        """Backward-compatible alias for older callers."""
        return self.job_compatibilities

    @property
    def best_match_job_index(self) -> int | None:
        """Backward-compatible alias for older callers."""
        return self.highest_compatibility_job_index

    @model_validator(mode="after")
    def validate_report(self) -> CompatibilityReport:
        indices = [job.job_index for job in self.job_compatibilities]
        if len(indices) != len(set(indices)):
            raise ValueError("job compatibility indices must be unique")
        index_set = set(indices)
        if self.highest_compatibility_job_index is not None and self.highest_compatibility_job_index not in index_set:
            raise ValueError("highest_compatibility_job_index must refer to a reported job")
        expected_average = _round_score(
            sum(job.compatibility_score for job in self.job_compatibilities) / len(self.job_compatibilities)
        )
        if abs(self.average_compatibility_score - expected_average) > SCORE_TOLERANCE:
            raise ValueError("average_compatibility_score must equal the average job score")
        expected_highest = max(
            self.job_compatibilities,
            key=lambda job: (job.compatibility_score, -job.job_index),
        ).job_index
        if self.highest_compatibility_job_index != expected_highest:
            raise ValueError("highest_compatibility_job_index must identify the highest score")
        if self.methodology_version != COMPATIBILITY_METHODOLOGY_VERSION:
            raise ValueError("methodology_version is not supported")
        if "probabilidad de contratación" not in self.disclaimer and "hiring probability" not in self.disclaimer:
            raise ValueError("compatibility disclaimer must explain that scores are not hiring probabilities")
        _validate_finite(self.average_compatibility_score, "average_compatibility_score")
        return self


def compatibility_band_for_score(score: float) -> str:
    """Return the band identifier for a decimal score."""
    _validate_finite(score, "score")
    for band, (minimum, maximum) in COMPATIBILITY_BANDS.items():
        if minimum <= score <= maximum:
            return band
    return CompatibilityBand.VERY_LOW.value if score < 0 else CompatibilityBand.VERY_HIGH.value


def _round_score(value: float) -> float:
    return round(value + 0.0000000001, 1)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _validate_finite(value: float, field_name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} cannot be NaN or infinite")


def _validate_finite_optional(value: float | None, field_name: str) -> None:
    if value is not None:
        _validate_finite(value, field_name)
