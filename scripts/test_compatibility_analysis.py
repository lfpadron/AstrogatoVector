"""Manual smoke test for compatibility analysis with fictitious data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.compatibility_analysis_models import (  # noqa: E402
    CompatibilitySemanticEvaluation,
    JobCompatibilitySemanticEvaluation,
    SemanticRequirementMatch,
)
from schemas.enums import EvidenceStatus, OutputLanguage, PriorityLevel, RequirementCoverage, SeniorityLevel, SkillCategory  # noqa: E402
from schemas.evidence_models import (  # noqa: E402
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.market_models import JobAnalysis, JobRequirement, TargetMarketAnalysis  # noqa: E402
from services.compatibility_audit_service import audit_compatibility_report, audit_semantic_compatibility  # noqa: E402
from services.compatibility_pipeline import run_compatibility_pipeline  # noqa: E402
from services.compatibility_scoring_service import CompatibilityScoringService  # noqa: E402
from services.openai_config import OpenAIConfigurationError, load_openai_settings  # noqa: E402


def main() -> None:
    args = _parse_args()
    profile = _candidate_profile()
    market = _market_analysis()

    try:
        load_openai_settings()
        run = run_compatibility_pipeline(profile, market, OutputLanguage.ES)
        if run.result.success and run.result.compatibility_report is not None:
            print("Evaluación OpenAI ejecutada y auditada correctamente.")
            _print_openai_metadata(run.result)
            _print_report(run.result.compatibility_report, args.show_details)
            return
        print("OpenAI respondió, pero no se obtuvo un reporte válido.")
        print(f"Categoría: {run.result.error_category or 'no_disponible'}")
        _print_openai_metadata(run.result)
        print(run.result.user_message or "Sin mensaje de usuario.")
    except OpenAIConfigurationError:
        print("Configuración OpenAI incompleta. Se ejecuta demo local con evaluación semántica ficticia.")

    evaluation = _semantic_evaluation(profile, market)
    semantic_audit = audit_semantic_compatibility(evaluation, profile, market)
    report = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    report_audit = audit_compatibility_report(report, evaluation, market)
    print(f"Auditoría semántica: {'OK' if semantic_audit.passed else 'FALLÓ'}")
    print(f"Auditoría matemática: {'OK' if report_audit.passed else 'FALLÓ'}")
    _print_report(report, args.show_details)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prueba ficticia de compatibilidad Astrogato Vector.")
    parser.add_argument("--show-details", action="store_true", help="Muestra dimensiones por vacante.")
    return parser.parse_args()


def _print_report(report, show_details: bool) -> None:
    print(f"Vacante con mayor alineación: {report.highest_compatibility_job_index}")
    print(f"Score promedio: {report.average_compatibility_score:.1f}")
    for job in report.job_compatibilities:
        print(f"Vacante {job.job_index}: {job.compatibility_score:.1f} | {job.compatibility_band}")
        if job.critical_gaps:
            print("  Brechas críticas:")
            for gap in job.critical_gaps:
                print(f"  - {gap}")
        if show_details:
            print("  Dimensiones:")
            for dimension in job.dimensions:
                score = "No solicitada" if dimension.score is None else f"{dimension.score:.1f}"
                print(f"  - {dimension.display_name}: {score} | peso efectivo {dimension.effective_weight:.0%}")


def _print_openai_metadata(result) -> None:
    print(f"Modelo: {result.model_used or 'no_disponible'}")
    print(f"Latencia ms: {result.latency_ms if result.latency_ms is not None else 'no_disponible'}")
    print(
        "Tokens: "
        f"entrada={result.input_tokens if result.input_tokens is not None else 'no_disponible'}, "
        f"salida={result.output_tokens if result.output_tokens is not None else 'no_disponible'}, "
        f"total={result.total_tokens if result.total_tokens is not None else 'no_disponible'}"
    )


def _candidate_profile() -> CandidateProfessionalProfile:
    ref = EvidenceReference(
        source_section="CV ficticio - Experiencia",
        source_excerpt="Project Manager con 7 años, Agile, riesgos, stakeholders, liderazgo de equipos y Jira.",
    )
    responsibility = EvidenceItem(
        statement="Project Manager con Agile, gestión de riesgos, stakeholders, liderazgo de equipos y Jira.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.92,
        references=[ref],
    )
    english = EvidenceItem(
        statement="Inglés intermedio.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LANGUAGE,
        confidence=0.85,
        references=[EvidenceReference(source_section="CV ficticio - Idiomas", source_excerpt="Inglés intermedio.")],
    )
    spanish = EvidenceItem(
        statement="Español nativo.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LANGUAGE,
        confidence=0.95,
        references=[EvidenceReference(source_section="CV ficticio - Idiomas", source_excerpt="Español nativo.")],
    )
    jira = CandidateSkill(
        name="Jira",
        normalized_name="jira",
        category=SkillCategory.TOOL,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.9,
        references=[ref],
    )
    agile = CandidateSkill(
        name="Agile",
        normalized_name="agile",
        category=SkillCategory.BUSINESS,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.93,
        references=[ref],
    )
    return CandidateProfessionalProfile(
        professional_identity="Project Manager",
        targetable_roles=["Project Manager", "Program Manager"],
        summary="Project Manager ficticio con siete años en Agile, riesgos, stakeholders y liderazgo de equipos.",
        total_years_experience=7,
        seniority=SeniorityLevel.MANAGER,
        industries=["Tecnología"],
        employment_history=[
            EmploymentEntry(
                employer="Empresa Ficticia",
                role_title="Project Manager",
                start_date="2018",
                end_date="2025",
                responsibilities=[responsibility],
                technologies=[jira],
                industries=["Tecnología"],
            )
        ],
        skills=[agile, jira],
        leadership_capabilities=[responsibility],
        languages=[spanish, english],
        missing_information=["Sin AWS.", "Sin Kubernetes.", "Sin certificación PMP."],
    )


def _market_analysis() -> TargetMarketAnalysis:
    pm = _req("Project Management", SkillCategory.BUSINESS, True, PriorityLevel.HIGH)
    agile = _req("Agile", SkillCategory.BUSINESS, True, PriorityLevel.HIGH)
    risks = _req("Gestión de riesgos", SkillCategory.BUSINESS, True, PriorityLevel.HIGH)
    stakeholders = _req("Stakeholders", SkillCategory.COMMUNICATION, True, PriorityLevel.HIGH)
    jira = _req("Jira", SkillCategory.TOOL, True, PriorityLevel.MEDIUM)
    english_desired = _req("Inglés avanzado", SkillCategory.LANGUAGE, False, PriorityLevel.MEDIUM)
    program = _req("Program Management", SkillCategory.BUSINESS, True, PriorityLevel.HIGH)
    aws = _req("AWS", SkillCategory.TOOL, True, PriorityLevel.CRITICAL)
    kubernetes = _req("Kubernetes", SkillCategory.TOOL, True, PriorityLevel.HIGH)
    english_required = _req("Inglés avanzado", SkillCategory.LANGUAGE, True, PriorityLevel.HIGH)
    leadership = _req("Liderazgo", SkillCategory.LEADERSHIP, True, PriorityLevel.HIGH)
    pmp = _req("PMP", SkillCategory.TOOL, False, PriorityLevel.MEDIUM)
    return TargetMarketAnalysis(
        target_role_family="Gestión de proyectos tecnológicos",
        suggested_target_titles=["Project Manager", "Program Manager"],
        dominant_seniority=SeniorityLevel.MANAGER,
        market_summary="Mercado ficticio para validar compatibilidad explicable.",
        common_responsibilities=["gestionar proyectos", "coordinar stakeholders"],
        common_requirements=[pm, agile, stakeholders, english_required],
        technical_skills=["AWS", "Kubernetes"],
        leadership_skills=["Liderazgo"],
        business_skills=["Project Management", "Program Management", "Agile"],
        tools_and_technologies=["Jira", "AWS", "Kubernetes"],
        industries=["Tecnología"],
        differentiators=["Cloud y contenedores"],
        job_analyses=[
            JobAnalysis(
                job_index=1,
                title="Senior Project Manager",
                company="Empresa Ejemplo",
                inferred_seniority=SeniorityLevel.MANAGER,
                role_summary="Vacante ficticia para Project Management con Agile, riesgos, stakeholders y Jira.",
                responsibilities=["gestionar proyectos", "coordinar stakeholders"],
                requirements=[pm, agile, risks, stakeholders, jira, english_desired],
                tools_and_technologies=["Jira"],
                language_requirements=["Inglés avanzado deseable"],
            ),
            JobAnalysis(
                job_index=2,
                title="Program Manager Cloud",
                company="Compañía Ficticia",
                inferred_seniority=SeniorityLevel.DIRECTOR,
                role_summary="Vacante ficticia para Program Management, AWS, Kubernetes e inglés avanzado obligatorio.",
                responsibilities=["liderar programas cloud"],
                requirements=[program, aws, kubernetes, english_required, leadership, pmp],
                tools_and_technologies=["AWS", "Kubernetes"],
                language_requirements=["Inglés avanzado obligatorio"],
                certifications=["PMP deseable"],
            ),
        ],
    )


def _req(name: str, category: SkillCategory, required: bool, priority: PriorityLevel) -> JobRequirement:
    return JobRequirement(
        name=name,
        normalized_name=name.casefold(),
        category=category,
        description=f"Requisito ficticio: {name}.",
        required=required,
        importance=priority,
        exact_keywords=[name],
    )


def _semantic_evaluation(profile: CandidateProfessionalProfile, market: TargetMarketAnalysis) -> CompatibilitySemanticEvaluation:
    evidence = profile.leadership_capabilities[0]
    english = profile.languages[1]
    return CompatibilitySemanticEvaluation(
        job_evaluations=[
            JobCompatibilitySemanticEvaluation(
                job_index=1,
                job_title="Senior Project Manager",
                company="Empresa Ejemplo",
                requirement_matches=[
                    _match(1, "Project Management", SkillCategory.BUSINESS, True, PriorityLevel.HIGH, RequirementCoverage.FULL, EvidenceStatus.SUPPORTED, evidence),
                    _match(1, "Agile", SkillCategory.BUSINESS, True, PriorityLevel.HIGH, RequirementCoverage.FULL, EvidenceStatus.SUPPORTED, evidence),
                    _match(1, "Gestión de riesgos", SkillCategory.BUSINESS, True, PriorityLevel.HIGH, RequirementCoverage.FULL, EvidenceStatus.SUPPORTED, evidence),
                    _match(1, "Stakeholders", SkillCategory.COMMUNICATION, True, PriorityLevel.HIGH, RequirementCoverage.FULL, EvidenceStatus.SUPPORTED, evidence),
                    _match(1, "Jira", SkillCategory.TOOL, True, PriorityLevel.MEDIUM, RequirementCoverage.FULL, EvidenceStatus.SUPPORTED, evidence),
                    _match(1, "Inglés avanzado", SkillCategory.LANGUAGE, False, PriorityLevel.MEDIUM, RequirementCoverage.PARTIAL, EvidenceStatus.SUPPORTED, english, missing=["nivel avanzado"]),
                ],
                strengths=["Project Management, Agile y stakeholders respaldados."],
                risks=["Inglés avanzado aparece solo parcialmente cubierto."],
                development_opportunities=["Preparar ejemplos de gestión de riesgos."],
                summary="Alta alineación demostrable para la vacante 1.",
            ),
            JobCompatibilitySemanticEvaluation(
                job_index=2,
                job_title="Program Manager Cloud",
                company="Compañía Ficticia",
                requirement_matches=[
                    _match(2, "Program Management", SkillCategory.BUSINESS, True, PriorityLevel.HIGH, RequirementCoverage.INDIRECT, EvidenceStatus.INFERRED, evidence, missing=["alcance de programas"]),
                    _match(2, "AWS", SkillCategory.TOOL, True, PriorityLevel.CRITICAL, RequirementCoverage.MISSING, EvidenceStatus.MISSING, None, missing=["AWS"]),
                    _match(2, "Kubernetes", SkillCategory.TOOL, True, PriorityLevel.HIGH, RequirementCoverage.MISSING, EvidenceStatus.MISSING, None, missing=["Kubernetes"]),
                    _match(2, "Inglés avanzado", SkillCategory.LANGUAGE, True, PriorityLevel.HIGH, RequirementCoverage.PARTIAL, EvidenceStatus.SUPPORTED, english, missing=["nivel avanzado"]),
                    _match(2, "Liderazgo", SkillCategory.LEADERSHIP, True, PriorityLevel.HIGH, RequirementCoverage.FULL, EvidenceStatus.SUPPORTED, evidence),
                    _match(2, "PMP", SkillCategory.TOOL, False, PriorityLevel.MEDIUM, RequirementCoverage.MISSING, EvidenceStatus.MISSING, None, missing=["certificación PMP"]),
                ],
                strengths=["Liderazgo respaldado."],
                risks=["AWS, Kubernetes y PMP no están respaldados."],
                development_opportunities=["Aprender AWS/Kubernetes antes de declararlos."],
                summary="Alineación moderada con brechas técnicas críticas para la vacante 2.",
            ),
        ]
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
        candidate_evidence=[evidence] if evidence else [],
        matched_candidate_items=[name] if evidence else [],
        missing_elements=missing or [],
        explanation=f"Evaluación ficticia para {name}.",
        confidence=0.88,
    )


if __name__ == "__main__":
    main()
