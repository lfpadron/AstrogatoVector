from __future__ import annotations

from schemas.compatibility_analysis_models import (
    CompatibilitySemanticEvaluation,
    JobCompatibilitySemanticEvaluation,
    SemanticRequirementMatch,
)
from schemas.enums import EvidenceStatus, PriorityLevel, RequirementCoverage, SkillCategory
from schemas.evidence_models import CandidateProfessionalProfile, EvidenceItem
from schemas.market_models import TargetMarketAnalysis
from tests.linkedin_profile_helpers import build_candidate_profile, build_market_analysis


def build_compatibility_inputs() -> tuple[CandidateProfessionalProfile, TargetMarketAnalysis, CompatibilitySemanticEvaluation]:
    profile = build_candidate_profile()
    market = build_market_analysis()
    return profile, market, build_semantic_evaluation(profile, market)


def build_semantic_evaluation(
    profile: CandidateProfessionalProfile | None = None,
    market: TargetMarketAnalysis | None = None,
) -> CompatibilitySemanticEvaluation:
    profile = profile or build_candidate_profile()
    market = market or build_market_analysis()
    evidence = profile.leadership_capabilities[0]
    return CompatibilitySemanticEvaluation(
        job_evaluations=[
            JobCompatibilitySemanticEvaluation(
                job_index=1,
                job_title=market.job_analyses[0].title,
                company=market.job_analyses[0].company,
                requirement_matches=[
                    _match(
                        1,
                        "Agile",
                        SkillCategory.BUSINESS,
                        True,
                        PriorityLevel.HIGH,
                        RequirementCoverage.FULL,
                        EvidenceStatus.SUPPORTED,
                        evidence,
                        ["Agile"],
                    ),
                    _match(
                        1,
                        "Stakeholder management",
                        SkillCategory.COMMUNICATION,
                        True,
                        PriorityLevel.HIGH,
                        RequirementCoverage.FULL,
                        EvidenceStatus.SUPPORTED,
                        evidence,
                        ["stakeholders"],
                    ),
                    _match(
                        1,
                        "Jira",
                        SkillCategory.TOOL,
                        False,
                        PriorityLevel.MEDIUM,
                        RequirementCoverage.FULL,
                        EvidenceStatus.SUPPORTED,
                        evidence,
                        ["Jira"],
                    ),
                ],
                strengths=["Agile y stakeholder management respaldados."],
                risks=[],
                development_opportunities=["Preparar ejemplos de gestión de riesgos."],
                summary="La vacante 1 muestra alta alineación demostrable.",
            ),
            JobCompatibilitySemanticEvaluation(
                job_index=2,
                job_title=market.job_analyses[1].title,
                company=market.job_analyses[1].company,
                requirement_matches=[
                    _match(
                        2,
                        "Stakeholder management",
                        SkillCategory.COMMUNICATION,
                        True,
                        PriorityLevel.HIGH,
                        RequirementCoverage.PARTIAL,
                        EvidenceStatus.SUPPORTED,
                        evidence,
                        ["stakeholders"],
                        ["alcance de Program Management"],
                    ),
                    _match(
                        2,
                        "Kubernetes",
                        SkillCategory.TOOL,
                        True,
                        PriorityLevel.HIGH,
                        RequirementCoverage.MISSING,
                        EvidenceStatus.MISSING,
                        None,
                        [],
                        ["experiencia práctica con Kubernetes"],
                    ),
                ],
                strengths=["Stakeholder management parcialmente respaldado."],
                risks=["Kubernetes no está respaldado en el perfil."],
                development_opportunities=["Adquirir práctica verificable con Kubernetes antes de declararlo."],
                summary="La vacante 2 tiene brechas técnicas importantes.",
            ),
        ],
        global_notes=["Evaluación ficticia para pruebas unitarias."],
    )


def _match(
    job_index: int,
    name: str,
    category: SkillCategory,
    required: bool,
    priority: PriorityLevel,
    coverage: RequirementCoverage,
    status: EvidenceStatus,
    evidence: EvidenceItem | None,
    matched_items: list[str],
    missing: list[str] | None = None,
) -> SemanticRequirementMatch:
    return SemanticRequirementMatch(
        job_index=job_index,
        requirement_name=name,
        normalized_requirement=name.casefold(),
        category=category,
        required=required,
        priority=priority,
        coverage=coverage,
        candidate_evidence_status=status,
        candidate_evidence=[evidence.model_copy(deep=True)] if evidence is not None else [],
        matched_candidate_items=matched_items,
        missing_elements=missing or [],
        explanation=f"Evaluación ficticia de {name}.",
        confidence=0.9 if status == EvidenceStatus.SUPPORTED else 0.75,
    )
