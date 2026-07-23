"""Final LinkedIn positioning and ATS audit models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from schemas.base import StrictBaseModel
from schemas.enums import AuditSeverity, PriorityLevel

AuditSeverityValue = Literal["info", "low", "medium", "high", "critical"]
AuditPriority = Literal["Quick Wins", "Medium Effort", "Long Term"]

ALLOWED_AUDIT_CATEGORIES = {
    "Headline",
    "About",
    "Experience",
    "Skills",
    "ATS",
    "Keywords",
    "Consistency",
    "Readability",
    "Banner",
    "Leadership",
    "Market Alignment",
}
AUDIT_SCORE_LABELS = {
    "excellent": "Excelente",
    "very_good": "Muy bueno",
    "good": "Bueno",
    "acceptable": "Aceptable",
    "needs_improvement": "Requiere mejoras",
}
LINKEDIN_AUDIT_COMPONENT_WEIGHTS = {
    "Headline": 0.20,
    "About": 0.25,
    "Experience": 0.20,
    "Skills": 0.15,
    "Banner": 0.10,
    "Readability": 0.10,
}
ATS_AUDIT_COMPONENT_WEIGHTS = {
    "Cobertura keywords": 0.30,
    "Cobertura requisitos": 0.25,
    "Skills": 0.15,
    "Experiencia": 0.15,
    "Títulos": 0.10,
    "Consistencia": 0.05,
}
FINAL_AUDIT_METHODOLOGY_VERSION = "1.0"
FINAL_AUDIT_PROMPT_VERSION = "local-final-audit-v1"
FINAL_AUDIT_DISCLAIMER = (
    "Auditoría orientativa y explicable para LinkedIn y ATS. No representa el algoritmo real de LinkedIn, "
    "no reproduce un ATS específico y no garantiza entrevistas, rankings ni contratación."
)


class AuditFinding(StrictBaseModel):
    """One explainable and actionable audit finding."""

    severity: AuditSeverityValue
    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1200)
    impact: str = Field(min_length=1, max_length=1000)
    recommendation: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=8)
    priority: AuditPriority = "Medium Effort"

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        if "category" not in migrated and "area" in migrated:
            migrated["category"] = migrated["area"]
        if "description" not in migrated and "finding" in migrated:
            migrated["description"] = migrated["finding"]
        if "title" not in migrated and "finding" in migrated:
            migrated["title"] = str(migrated["finding"])[:120]
        migrated.pop("area", None)
        migrated.pop("finding", None)
        if "impact" not in migrated:
            migrated["impact"] = "Ayuda a priorizar mejoras del posicionamiento profesional."
        if migrated.get("recommendation") is None:
            migrated["recommendation"] = "Revisar este punto antes de publicar o postular."
        if isinstance(migrated.get("evidence"), str):
            migrated["evidence"] = [migrated["evidence"]]
        if "evidence" not in migrated or migrated.get("evidence") is None:
            migrated["evidence"] = []
        if "priority" in migrated:
            migrated["priority"] = _priority_to_audit_priority(migrated["priority"])
        else:
            migrated["priority"] = "Medium Effort"
        if "severity" in migrated:
            migrated["severity"] = _severity_to_prompt_value(migrated["severity"])
        return migrated

    @field_validator("category")
    @classmethod
    def category_must_be_allowed(cls, value: str) -> str:
        if value not in ALLOWED_AUDIT_CATEGORIES:
            raise ValueError("audit finding category is not allowed")
        return value

    @field_validator("recommendation")
    @classmethod
    def recommendation_must_be_actionable(cls, value: str) -> str:
        normalized = value.casefold().strip()
        if normalized in {"mejora tu perfil", "mejorar perfil", "improve your profile"}:
            raise ValueError("recommendation must be specific and actionable")
        return value

    @property
    def area(self) -> str:
        """Backward-compatible alias for earlier schema examples."""
        return self.category

    @property
    def finding(self) -> str:
        """Backward-compatible alias for earlier schema examples."""
        return self.description


class AuditRecommendation(StrictBaseModel):
    """Prioritized action derived from audit findings."""

    priority: AuditPriority
    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    action: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("category")
    @classmethod
    def category_must_be_allowed(cls, value: str) -> str:
        if value not in ALLOWED_AUDIT_CATEGORIES:
            raise ValueError("audit recommendation category is not allowed")
        return value


class AuditScoreComponent(StrictBaseModel):
    """One weighted score component."""

    name: str = Field(min_length=1, max_length=120)
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=100.0)
    explanation: str = Field(min_length=1, max_length=1000)


class LinkedInPositioningAudit(StrictBaseModel):
    """Explainable audit of LinkedIn positioning, not LinkedIn's ranking algorithm."""

    score: float = Field(ge=0.0, le=100.0)
    score_label: str = Field(min_length=1, max_length=80)
    components: list[AuditScoreComponent] = Field(min_length=6, max_length=6)
    findings: list[AuditFinding] = Field(default_factory=list)
    strengths: list[AuditFinding] = Field(default_factory=list)
    risks: list[AuditFinding] = Field(default_factory=list)
    quick_wins: list[AuditRecommendation] = Field(default_factory=list)
    recommendations: list[AuditRecommendation] = Field(default_factory=list)
    disclaimer: str = Field(default=FINAL_AUDIT_DISCLAIMER, min_length=20, max_length=1200)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_scores(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "score" in data:
            return data
        migrated = dict(data)
        component_values = {
            "Headline": migrated.get("clarity_score", 0),
            "About": migrated.get("credibility_score", 0),
            "Experience": migrated.get("consistency_score", 0),
            "Skills": migrated.get("keyword_coverage_score", 0),
            "Banner": migrated.get("credibility_score", 0),
            "Readability": migrated.get("readability_score", 0),
        }
        migrated["components"] = [
            AuditScoreComponent(
                name=name,
                weight=LINKEDIN_AUDIT_COMPONENT_WEIGHTS[name],
                score=float(score),
                explanation=f"Componente migrado desde el contrato previo: {name}.",
            ).model_dump()
            for name, score in component_values.items()
        ]
        migrated["score"] = _weighted_score(migrated["components"])
        migrated["score_label"] = score_label_for_score(migrated["score"])
        migrated.setdefault("strengths", [])
        migrated.setdefault("risks", [])
        migrated.setdefault("quick_wins", [])
        migrated.setdefault("recommendations", _actions_to_recommendations(migrated.get("prioritized_actions", [])))
        for field_name in (
            "clarity_score",
            "keyword_coverage_score",
            "consistency_score",
            "credibility_score",
            "readability_score",
            "overall_score",
            "prioritized_actions",
        ):
            migrated.pop(field_name, None)
        return migrated

    @model_validator(mode="after")
    def validate_components_and_score(self) -> LinkedInPositioningAudit:
        _validate_component_set(self.components, LINKEDIN_AUDIT_COMPONENT_WEIGHTS)
        expected_score = _weighted_score([component.model_dump() for component in self.components])
        if abs(self.score - expected_score) > 0.11:
            raise ValueError("LinkedIn audit score must equal the weighted component scores")
        if self.score_label != score_label_for_score(self.score):
            raise ValueError("LinkedIn audit score_label must match score")
        return self

    @property
    def overall_score(self) -> int:
        """Backward-compatible alias."""
        return round(self.score)

    @property
    def clarity_score(self) -> int:
        return _component_score(self.components, "Headline")

    @property
    def keyword_coverage_score(self) -> int:
        return _component_score(self.components, "Skills")

    @property
    def consistency_score(self) -> int:
        return _component_score(self.components, "Experience")

    @property
    def credibility_score(self) -> int:
        return _component_score(self.components, "About")

    @property
    def readability_score(self) -> int:
        return _component_score(self.components, "Readability")

    @property
    def prioritized_actions(self) -> list[str]:
        return [recommendation.action for recommendation in self.recommendations]


class ATSAudit(StrictBaseModel):
    """Explainable ATS-oriented estimation that does not reproduce a specific ATS."""

    score: float = Field(ge=0.0, le=100.0)
    score_label: str = Field(min_length=1, max_length=80)
    components: list[AuditScoreComponent] = Field(min_length=6, max_length=6)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    strengths: list[AuditFinding] = Field(default_factory=list)
    risks: list[AuditFinding] = Field(default_factory=list)
    quick_wins: list[AuditRecommendation] = Field(default_factory=list)
    recommendations: list[AuditRecommendation] = Field(default_factory=list)
    disclaimer: str = Field(default=FINAL_AUDIT_DISCLAIMER, min_length=20, max_length=1200)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_scores(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "score" in data:
            return data
        migrated = dict(data)
        component_values = {
            "Cobertura keywords": migrated.get("keyword_alignment_score", 0),
            "Cobertura requisitos": migrated.get("completeness_score", 0),
            "Skills": migrated.get("skills_alignment_score", 0),
            "Experiencia": migrated.get("experience_alignment_score", 0),
            "Títulos": migrated.get("experience_alignment_score", 0),
            "Consistencia": migrated.get("completeness_score", 0),
        }
        migrated["components"] = [
            AuditScoreComponent(
                name=name,
                weight=ATS_AUDIT_COMPONENT_WEIGHTS[name],
                score=float(score),
                explanation=f"Componente migrado desde el contrato previo: {name}.",
            ).model_dump()
            for name, score in component_values.items()
        ]
        migrated["score"] = _weighted_score(migrated["components"])
        migrated["score_label"] = score_label_for_score(migrated["score"])
        migrated.setdefault("strengths", [])
        migrated.setdefault("risks", [])
        migrated.setdefault("quick_wins", [])
        if migrated.get("recommendations") and all(isinstance(item, str) for item in migrated["recommendations"]):
            migrated["recommendations"] = _actions_to_recommendations(migrated["recommendations"])
        else:
            migrated.setdefault("recommendations", _actions_to_recommendations([]))
        for field_name in (
            "keyword_alignment_score",
            "experience_alignment_score",
            "skills_alignment_score",
            "completeness_score",
            "overall_score",
        ):
            migrated.pop(field_name, None)
        return migrated

    @model_validator(mode="after")
    def validate_components_and_score(self) -> ATSAudit:
        _validate_component_set(self.components, ATS_AUDIT_COMPONENT_WEIGHTS)
        expected_score = _weighted_score([component.model_dump() for component in self.components])
        if abs(self.score - expected_score) > 0.11:
            raise ValueError("ATS audit score must equal the weighted component scores")
        if self.score_label != score_label_for_score(self.score):
            raise ValueError("ATS audit score_label must match score")
        return self

    @property
    def overall_score(self) -> int:
        """Backward-compatible alias."""
        return round(self.score)

    @property
    def keyword_alignment_score(self) -> int:
        return _component_score(self.components, "Cobertura keywords")

    @property
    def experience_alignment_score(self) -> int:
        return _component_score(self.components, "Experiencia")

    @property
    def skills_alignment_score(self) -> int:
        return _component_score(self.components, "Skills")

    @property
    def completeness_score(self) -> int:
        return _component_score(self.components, "Cobertura requisitos")


class FinalAuditValidationFinding(StrictBaseModel):
    """One local validation finding for an AuditReport."""

    severity: Literal["error", "warning"]
    path: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=1000)


class FinalAuditValidationResult(StrictBaseModel):
    """Deterministic validation result for a final audit report."""

    passed: bool
    findings: list[FinalAuditValidationFinding] = Field(default_factory=list)


class AuditReport(StrictBaseModel):
    """Combined final audit output and safe stage metadata."""

    success: bool = True
    linkedin_positioning: LinkedInPositioningAudit | None = None
    ats_estimation: ATSAudit | None = None
    executive_summary: str | None = Field(default=None, max_length=1600)
    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    average_compatibility_score: float | None = Field(default=None, ge=0.0, le=100.0)
    findings: list[AuditFinding] = Field(default_factory=list)
    strengths: list[AuditFinding] = Field(default_factory=list)
    risks: list[AuditFinding] = Field(default_factory=list)
    quick_wins: list[AuditRecommendation] = Field(default_factory=list)
    recommendations: list[AuditRecommendation] = Field(default_factory=list)
    latency_ms: int | None = Field(default=None, ge=0)
    audit_passed: bool = False
    audit_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None
    user_message: str | None = None
    retryable: bool = False
    reused_from_session: bool = False
    prompt_version: str | None = FINAL_AUDIT_PROMPT_VERSION
    methodology_version: str | None = FINAL_AUDIT_METHODOLOGY_VERSION

    @model_validator(mode="before")
    @classmethod
    def fill_aggregate_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        linkedin = migrated.get("linkedin_positioning")
        ats = migrated.get("ats_estimation")
        if linkedin is not None and ats is not None:
            linkedin_model = linkedin if isinstance(linkedin, LinkedInPositioningAudit) else LinkedInPositioningAudit.model_validate(linkedin)
            ats_model = ats if isinstance(ats, ATSAudit) else ATSAudit.model_validate(ats)
            migrated.setdefault("overall_score", round((linkedin_model.score + ats_model.score) / 2, 1))
            migrated.setdefault("executive_summary", _default_executive_summary(linkedin_model.score, ats_model.score))
            migrated.setdefault("findings", _merge_findings(linkedin_model.findings, ats_model.findings))
            migrated.setdefault("strengths", _merge_findings(linkedin_model.strengths, ats_model.strengths))
            migrated.setdefault("risks", _merge_findings(linkedin_model.risks, ats_model.risks))
            migrated.setdefault("quick_wins", _merge_recommendations(linkedin_model.quick_wins, ats_model.quick_wins))
            migrated.setdefault("recommendations", _merge_recommendations(linkedin_model.recommendations, ats_model.recommendations))
        if migrated.get("success", True) is True and "audit_passed" not in migrated:
            migrated["audit_passed"] = True
        return migrated

    @model_validator(mode="after")
    def validate_report_consistency(self) -> AuditReport:
        if self.success and (self.linkedin_positioning is None or self.ats_estimation is None):
            raise ValueError("successful final audit must include LinkedIn and ATS audits")
        if not self.success and (self.linkedin_positioning is not None or self.ats_estimation is not None):
            raise ValueError("failed final audit cannot include audit outputs")
        if self.success and not self.audit_passed:
            raise ValueError("successful final audit must pass local validation")
        if self.success and self.overall_score is not None and self.linkedin_positioning and self.ats_estimation:
            expected = round((self.linkedin_positioning.score + self.ats_estimation.score) / 2, 1)
            if abs(self.overall_score - expected) > 0.11:
                raise ValueError("overall_score must average LinkedIn and ATS scores")
        if self.methodology_version != FINAL_AUDIT_METHODOLOGY_VERSION:
            raise ValueError("final audit methodology_version is not supported")
        return self


def score_label_for_score(score: float) -> str:
    """Return the required human score interpretation."""
    if score >= 90:
        return AUDIT_SCORE_LABELS["excellent"]
    if score >= 80:
        return AUDIT_SCORE_LABELS["very_good"]
    if score >= 70:
        return AUDIT_SCORE_LABELS["good"]
    if score >= 60:
        return AUDIT_SCORE_LABELS["acceptable"]
    return AUDIT_SCORE_LABELS["needs_improvement"]


def _validate_component_set(components: list[AuditScoreComponent], weights: dict[str, float]) -> None:
    names = [component.name for component in components]
    if set(names) != set(weights):
        raise ValueError("audit components must match the required methodology")
    if len(names) != len(set(names)):
        raise ValueError("audit components must be unique")
    for component in components:
        if abs(component.weight - weights[component.name]) > 0.000001:
            raise ValueError(f"{component.name} must have weight {weights[component.name]}")


def _weighted_score(component_payloads: list[dict[str, Any]]) -> float:
    return round(sum(float(component["score"]) * float(component["weight"]) for component in component_payloads), 1)


def _component_score(components: list[AuditScoreComponent], name: str) -> int:
    for component in components:
        if component.name == name:
            return round(component.score)
    return 0


def _severity_to_prompt_value(value: object) -> str:
    raw = str(getattr(value, "value", value)).casefold()
    if raw == AuditSeverity.CRITICAL.value:
        return "critical"
    if raw == getattr(AuditSeverity, "WARNING").value:
        return "medium"
    if raw == getattr(AuditSeverity, "PASS").value:
        return "info"
    if raw in {"info", "low", "medium", "high", "critical"}:
        return raw
    return "medium"


def _priority_to_audit_priority(value: object) -> str:
    raw = str(getattr(value, "value", value)).casefold()
    if raw in {"quick wins", "quick_win", "quick-wins", "quick win"}:
        return "Quick Wins"
    if raw in {"medium effort", "medium_effort", "medium-effort"}:
        return "Medium Effort"
    if raw in {"long term", "long_term", "long-term"}:
        return "Long Term"
    if raw in {PriorityLevel.CRITICAL.value, PriorityLevel.HIGH.value}:
        return "Quick Wins"
    if raw == PriorityLevel.MEDIUM.value:
        return "Medium Effort"
    return "Long Term"


def _actions_to_recommendations(actions: list[str]) -> list[dict[str, Any]]:
    return [
        AuditRecommendation(
            priority="Medium Effort",
            category="Consistency",
            title="Acción priorizada",
            action=action,
            rationale="Acción migrada desde el contrato previo.",
            evidence=[],
        ).model_dump()
        for action in actions
    ]


def _merge_findings(*groups: list[AuditFinding]) -> list[dict[str, Any]]:
    seen = set()
    merged: list[dict[str, Any]] = []
    for group in groups:
        for finding in group:
            key = (finding.severity, finding.category, finding.title, finding.description)
            if key in seen:
                continue
            seen.add(key)
            merged.append(finding.model_dump())
    return merged


def _merge_recommendations(*groups: list[AuditRecommendation]) -> list[dict[str, Any]]:
    seen = set()
    merged: list[dict[str, Any]] = []
    for group in groups:
        for recommendation in group:
            key = (recommendation.priority, recommendation.category, recommendation.action)
            if key in seen:
                continue
            seen.add(key)
            merged.append(recommendation.model_dump())
    return merged


def _default_executive_summary(linkedin_score: float, ats_score: float) -> str:
    return (
        f"El posicionamiento LinkedIn quedó en nivel {score_label_for_score(linkedin_score)} "
        f"({linkedin_score:.1f}/100) y la lectura ATS quedó en nivel {score_label_for_score(ats_score)} "
        f"({ats_score:.1f}/100). Revisa hallazgos y Quick Wins antes de publicar o postular."
    )
