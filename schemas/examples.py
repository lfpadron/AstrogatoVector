"""Fictitious examples for documentation, tests and future prompts."""

from __future__ import annotations

from schemas.audit_models import (
    ATS_AUDIT_COMPONENT_WEIGHTS,
    LINKEDIN_AUDIT_COMPONENT_WEIGHTS,
    ATSAudit,
    AuditFinding,
    AuditRecommendation,
    AuditReport,
    AuditScoreComponent,
    LinkedInPositioningAudit,
    score_label_for_score,
)
from schemas.communication_models import CommunicationOutput, CoverLetter, ProfessionalMessage
from schemas.compatibility_models import (
    COMPATIBILITY_DIMENSION_LABELS_ES,
    COMPATIBILITY_DIMENSION_WEIGHTS,
    COMPATIBILITY_DISCLAIMER_ES,
    COMPATIBILITY_METHODOLOGY_VERSION,
    CompatibilityDimension,
    CompatibilityReport,
    JobCompatibility,
    RequirementMatch,
    compatibility_band_for_score,
)
from schemas.content_models import FourWeekContentPlan, LinkedInPostSuggestion
from schemas.enums import (
    CompatibilityDimensionName,
    ContentSource,
    EvidenceStatus,
    OutputLanguage,
    PriorityLevel,
    ProfessionalMessageType,
    RequirementCoverage,
    SeniorityLevel,
    SkillCategory,
)
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.input_models import CandidateInput, DocumentParseSummary, JobInput
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis
from schemas.profile_models import (
    ATSKeyword,
    AboutOutput,
    BannerContent,
    HeadlineOutput,
    LinkedInProfileOutput,
    PrioritizedSkill,
    RewrittenExperienceEntry,
)
from schemas.result_models import ApplicationResult

EXAMPLE_CV_TEXT = (
    "María Ejemplo es Project Manager ficticia con experiencia demostrativa en coordinación "
    "de equipos, seguimiento de indicadores, comunicación ejecutiva, mejora de procesos, "
    "planeación de roadmap, gestión de riesgos y colaboración con áreas de producto, datos "
    "y tecnología dentro de Empresa Demostración."
)
EXAMPLE_JOB_DESCRIPTION = (
    "Responsable de liderar iniciativas estratégicas, coordinar equipos multifuncionales, "
    "analizar métricas de negocio, priorizar roadmap, comunicar avances ejecutivos y mejorar "
    "procesos operativos para productos digitales en crecimiento."
)
GENERIC_DISCLAIMER = (
    "Resultado orientativo generado para revisión humana; no garantiza entrevistas, "
    "contrataciones, ranking en LinkedIn ni compatibilidad con un sistema ATS específico."
)


def build_example_candidate_input() -> CandidateInput:
    """Build a minimal valid normalized input with fictitious data."""
    return CandidateInput(
        cv_text=EXAMPLE_CV_TEXT,
        cv_source=ContentSource.TEXT,
        cv_parse_summary=DocumentParseSummary(
            source=ContentSource.TEXT,
            character_count=len(EXAMPLE_CV_TEXT),
            word_count=len(EXAMPLE_CV_TEXT.split()),
        ),
        linkedin_text=None,
        linkedin_source=ContentSource.GENERATED,
        output_language=OutputLanguage.ES,
        jobs=[
            JobInput(
                index=1,
                title="Project Manager",
                company="Empresa Demostración",
                description=EXAMPLE_JOB_DESCRIPTION,
                source=ContentSource.TEXT,
            ),
            JobInput(
                index=2,
                title="Program Manager",
                company="Compañía Ficticia",
                description=EXAMPLE_JOB_DESCRIPTION,
                source=ContentSource.TEXT,
            ),
        ],
    )


def build_example_professional_profile() -> CandidateProfessionalProfile:
    """Build a minimal valid professional profile with evidence references."""
    reference = _reference()
    coordination = EvidenceItem(
        statement="Ha coordinado equipos multifuncionales para iniciativas de producto.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.86,
        references=[reference],
    )
    skill = CandidateSkill(
        name="Gestión de proyectos",
        normalized_name="gestion de proyectos",
        category=SkillCategory.BUSINESS,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.9,
        years_experience=None,
        references=[reference],
    )
    achievement = Achievement(
        description="Mejoró el seguimiento de indicadores de producto en un entorno ficticio.",
        measurable_result=None,
        evidence_status=EvidenceStatus.SUPPORTED,
        references=[reference],
    )
    employment = EmploymentEntry(
        employer="Empresa Demostración",
        role_title="Project Manager",
        start_date="2021",
        end_date=None,
        is_current=True,
        location="Remoto",
        responsibilities=[coordination],
        achievements=[achievement],
        technologies=[skill],
        industries=["Tecnología"],
    )
    return CandidateProfessionalProfile(
        professional_identity="Project Manager orientada a productos digitales",
        targetable_roles=["Project Manager", "Program Manager"],
        summary=(
            "Perfil ficticio con experiencia en coordinación de equipos, análisis de métricas "
            "y comunicación ejecutiva para iniciativas de producto digital."
        ),
        total_years_experience=None,
        seniority=SeniorityLevel.MANAGER,
        industries=["Tecnología"],
        employment_history=[employment],
        skills=[skill],
        leadership_capabilities=[coordination],
        achievements=[achievement],
        missing_information=["Fechas exactas y métricas cuantitativas requieren revisión."],
    )


def build_example_market_analysis() -> TargetMarketAnalysis:
    """Build a minimal valid target market analysis."""
    requirement = JobRequirement(
        name="Coordinación de equipos",
        normalized_name="coordinacion de equipos",
        category=SkillCategory.LEADERSHIP,
        description="Coordinar equipos multifuncionales para ejecutar iniciativas de producto.",
        required=True,
        importance=PriorityLevel.HIGH,
        exact_keywords=["cross-functional teams", "stakeholders"],
    )
    job_analyses = [
        JobAnalysis(
            job_index=1,
            title="Project Manager",
            company="Empresa Demostración",
            inferred_seniority=SeniorityLevel.MANAGER,
            role_summary="Rol ficticio enfocado en coordinación, métricas y ejecución de producto.",
            responsibilities=["Coordinar equipos", "Reportar avances"],
            requirements=[requirement],
            leadership_skills=["Coordinación"],
            exact_keywords=["roadmap", "stakeholders"],
        ),
        JobAnalysis(
            job_index=2,
            title="Program Manager",
            company="Compañía Ficticia",
            inferred_seniority=SeniorityLevel.MANAGER,
            role_summary="Rol ficticio orientado a gestión de programas y comunicación ejecutiva.",
            responsibilities=["Gestionar programas", "Alinear prioridades"],
            requirements=[requirement],
            leadership_skills=["Alineación ejecutiva"],
            exact_keywords=["program management", "metrics"],
        ),
    ]
    return TargetMarketAnalysis(
        target_role_family="Gestión de proyectos y programas",
        suggested_target_titles=["Project Manager", "Program Manager"],
        dominant_seniority=SeniorityLevel.MANAGER,
        market_summary=(
            "Las vacantes ficticias priorizan coordinación multifuncional, comunicación clara "
            "y seguimiento de métricas para productos digitales."
        ),
        common_responsibilities=["Coordinar equipos", "Comunicar avances"],
        common_requirements=[requirement],
        keywords=[
            MarketKeyword(
                keyword="Stakeholder management",
                normalized_keyword="stakeholder management",
                frequency=2,
                job_indices=[1, 2],
                category=SkillCategory.COMMUNICATION,
                priority=PriorityLevel.HIGH,
            )
        ],
        leadership_skills=["Coordinación", "Comunicación ejecutiva"],
        business_skills=["Priorización", "Gestión de riesgos"],
        tools_and_technologies=["Dashboards"],
        industries=["Tecnología"],
        differentiators=["Capacidad de conectar ejecución con métricas"],
        job_analyses=job_analyses,
    )


def build_example_linkedin_profile() -> LinkedInProfileOutput:
    """Build a minimal valid LinkedIn profile output."""
    headline_text = "Project Manager | Producto digital, métricas y coordinación ejecutiva"
    about_text = (
        "Soy una Project Manager ficticia enfocada en convertir prioridades de negocio en "
        "planes claros de ejecución para productos digitales. He trabajado con equipos "
        "multifuncionales, métricas de seguimiento y comunicación ejecutiva para mantener "
        "alineadas a las áreas involucradas. Este ejemplo existe solo para validar contratos "
        "de datos y no representa a una persona real."
    )
    rewritten = (
        "Coordiné iniciativas ficticias de producto digital, alineando prioridades, seguimiento "
        "de riesgos, comunicación ejecutiva y colaboración entre equipos de negocio, datos y tecnología."
    )
    return LinkedInProfileOutput(
        banner=BannerContent(
            primary_line="Project Manager",
            specialty_line="Producto digital, métricas y ejecución",
            supporting_line="Coordinación multifuncional",
            visual_concept="Banner sobrio con bloques de roadmap y métricas representadas en texto.",
            recommended_template="professional_light",
        ),
        headline=HeadlineOutput(
            text=headline_text,
            character_count=len(headline_text),
            included_keywords=["Project Manager", "métricas"],
        ),
        about=AboutOutput(
            text=about_text,
            character_count=len(about_text),
            included_keywords=["producto digital", "comunicación ejecutiva"],
        ),
        experience=[
            RewrittenExperienceEntry(
                source_role_title="Project Manager",
                suggested_role_title="Project Manager de Producto Digital",
                employer="Empresa Demostración",
                rewritten_text=rewritten,
                included_keywords=["roadmap", "stakeholders"],
            )
        ],
        prioritized_skills=[
            PrioritizedSkill(
                name="Gestión de proyectos",
                category=SkillCategory.BUSINESS,
                priority_rank=1,
                evidence_status=EvidenceStatus.SUPPORTED,
                rationale="Aparece en CV ficticio y coincide con las vacantes objetivo.",
                recommended_placement=["Skills", "About"],
            )
        ],
        ats_keywords=[
            ATSKeyword(
                keyword="Stakeholder management",
                normalized_keyword="stakeholder management",
                priority=PriorityLevel.HIGH,
                frequency_in_jobs=2,
                supported_by_candidate=True,
                evidence_status=EvidenceStatus.SUPPORTED,
                recommended_sections=["Headline", "Experience"],
            )
        ],
        global_review_notes=["Revisar que las métricas no se inventen antes de publicar."],
    )


def build_example_compatibility_report() -> CompatibilityReport:
    """Build a valid compatibility report with mathematically consistent scores."""
    jobs = [
        _job_compatibility(1, "Project Manager", "Empresa Demostración", [80, 75, 70, 85, 60, 65]),
        _job_compatibility(2, "Program Manager", "Compañía Ficticia", [70, 70, 70, 70, 70, 70]),
    ]
    return CompatibilityReport(
        job_compatibilities=jobs,
        highest_compatibility_job_index=1,
        average_compatibility_score=round(sum(job.compatibility_score for job in jobs) / len(jobs), 1),
        common_strengths=["Coordinación de equipos"],
        common_gaps=["Certificación PMP no respaldada"],
        strategic_recommendations=[
            "La vacante 1 presenta la mayor alineación demostrable entre las ofertas analizadas.",
            "Validar brechas antes de adaptar el perfil.",
        ],
        methodology_version=COMPATIBILITY_METHODOLOGY_VERSION,
        disclaimer=COMPATIBILITY_DISCLAIMER_ES,
    )


def build_example_audit_report() -> AuditReport:
    """Build a valid audit report."""
    finding = AuditFinding(
        severity="info",
        category="Headline",
        title="Headline claro",
        description="El titular ficticio comunica rol objetivo y foco de mercado.",
        impact="Facilita lectura rápida del posicionamiento profesional.",
        recommendation="Mantener keywords respaldadas por evidencia.",
        evidence=["Project Manager | Producto digital"],
        priority="Quick Wins",
    )
    recommendation = AuditRecommendation(
        priority="Quick Wins",
        category="Headline",
        title="Mantener keyword principal",
        action="Conservar una keyword respaldada en el headline.",
        rationale="Ayuda a mantener consistencia con el mercado objetivo.",
        evidence=["Headline ficticio"],
    )
    return AuditReport(
        linkedin_positioning=LinkedInPositioningAudit(
            score=82,
            score_label=score_label_for_score(82),
            components=[
                AuditScoreComponent(name=name, weight=weight, score=82, explanation=f"Componente ficticio {name}.")
                for name, weight in LINKEDIN_AUDIT_COMPONENT_WEIGHTS.items()
            ],
            findings=[finding],
            strengths=[finding],
            risks=[],
            quick_wins=[recommendation],
            recommendations=[recommendation],
        ),
        ats_estimation=ATSAudit(
            score=77,
            score_label=score_label_for_score(77),
            components=[
                AuditScoreComponent(name=name, weight=weight, score=77, explanation=f"Componente ficticio {name}.")
                for name, weight in ATS_AUDIT_COMPONENT_WEIGHTS.items()
            ],
            matched_keywords=["stakeholder management"],
            missing_keywords=["budget ownership"],
            findings=[finding],
            strengths=[],
            risks=[],
            quick_wins=[recommendation],
            recommendations=[recommendation],
        ),
    )


def build_example_communication_output() -> CommunicationOutput:
    """Build valid professional communications."""
    body = (
        "Estimada persona reclutadora, comparto mi interés ficticio por la posición indicada. "
        "Mi experiencia demostrativa se centra en coordinación de equipos, seguimiento de métricas "
        "y comunicación ejecutiva para productos digitales. Antes de enviar esta carta, deben "
        "personalizarse logros, empresa, tono y evidencia real para evitar afirmaciones no respaldadas."
    )
    return CommunicationOutput(
        headhunter_messages=[
            ProfessionalMessage(
                message_type=ProfessionalMessageType.CONNECTION_REQUEST,
                purpose="Iniciar contacto profesional con una persona reclutadora.",
                text="Hola, me interesa conectar por oportunidades de Project Management en productos digitales.",
                target_role="Project Manager",
                personalization_required=["Nombre de la persona", "Empresa objetivo"],
            )
        ],
        cover_letters=[
            CoverLetter(
                job_index=1,
                job_title="Project Manager",
                company="Empresa Demostración",
                subject="Interés en Project Manager",
                body=body,
                evidence_used=["Coordinación de equipos"],
                personalization_required=["Nombre de la vacante"],
            ),
            CoverLetter(
                job_index=2,
                job_title="Program Manager",
                company="Compañía Ficticia",
                subject="Interés en Program Manager",
                body=body,
                evidence_used=["Comunicación ejecutiva"],
                personalization_required=["Prioridades del programa"],
            ),
        ],
    )


def build_example_content_plan() -> FourWeekContentPlan:
    """Build a valid four-week content plan."""
    posts = []
    for week in range(1, 5):
        for publication_number in range(1, 3):
            posts.append(
                LinkedInPostSuggestion(
                    week=week,
                    publication_number=publication_number,
                    theme=f"Tema ficticio semana {week}.{publication_number}",
                    objective="Mostrar aprendizaje profesional sin revelar datos sensibles.",
                    draft_text=(
                        "Publicación ficticia para validar el contrato de contenidos. Describe una "
                        "reflexión profesional sobre coordinación, métricas y comunicación ejecutiva, "
                        "sin mencionar datos reales ni logros que no estén respaldados por evidencia."
                    ),
                    call_to_action="¿Qué práctica te ayuda a mantener alineado a un equipo?",
                    evidence_basis=["Experiencia ficticia de coordinación"],
                    placeholders_to_complete=["Ejemplo real validado por la persona usuaria"],
                    suggested_hashtags=["#ProjectManagement", "#ProductoDigital"],
                )
            )
    return FourWeekContentPlan(
        posts=posts,
        editorial_notes=["Plan ficticio de validación; requiere revisión humana antes de usarse."],
    )


def build_example_application_result() -> ApplicationResult:
    """Build the complete fictitious application result."""
    return ApplicationResult(
        output_language=OutputLanguage.ES,
        candidate_profile=build_example_professional_profile(),
        target_market=build_example_market_analysis(),
        linkedin_profile=build_example_linkedin_profile(),
        compatibility=build_example_compatibility_report(),
        audits=build_example_audit_report(),
        communication=build_example_communication_output(),
        content_plan=build_example_content_plan(),
        global_warnings=["Ejemplo ficticio para validar serialización."],
        disclaimer=GENERIC_DISCLAIMER,
    )


def _reference() -> EvidenceReference:
    return EvidenceReference(
        source_section="CV ficticio - Experiencia",
        source_excerpt="Coordinación de equipos, seguimiento de indicadores y comunicación ejecutiva.",
    )


def _job_compatibility(
    index: int,
    title: str,
    company: str,
    raw_scores: list[float],
) -> JobCompatibility:
    dimensions = []
    for name, raw_score in zip(COMPATIBILITY_DIMENSION_WEIGHTS, raw_scores, strict=True):
        weight = COMPATIBILITY_DIMENSION_WEIGHTS[name]
        dimensions.append(
            CompatibilityDimension(
                dimension_id=CompatibilityDimensionName(name),
                display_name=COMPATIBILITY_DIMENSION_LABELS_ES[name],
                original_weight=weight,
                effective_weight=weight,
                evaluated=True,
                score=raw_score,
                total_requirements=1,
                full_matches=1 if raw_score >= 80 else 0,
                partial_matches=1 if 55 <= raw_score < 80 else 0,
                indirect_matches=0,
                missing_matches=1 if raw_score < 55 else 0,
                conflict_matches=0,
                explanation=f"Dimensión ficticia calculada para {name}.",
            )
        )
    total = round(sum((dimension.score or 0) * dimension.effective_weight for dimension in dimensions), 1)
    evidence = EvidenceItem(
        statement="Coordinación de equipos, seguimiento de indicadores y comunicación ejecutiva.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.9,
        references=[_reference()],
    )
    match = RequirementMatch(
        requirement_name="Coordinación de equipos",
        normalized_requirement="coordinacion de equipos",
        category=SkillCategory.LEADERSHIP,
        dimension_id=CompatibilityDimensionName.LEADERSHIP_MANAGEMENT,
        required=True,
        priority=PriorityLevel.HIGH,
        coverage=RequirementCoverage.FULL,
        evidence_status=EvidenceStatus.SUPPORTED,
        coverage_points=1.0,
        evidence_factor=1.0,
        weighted_match_value=1.5,
        candidate_evidence=[evidence],
        matched_candidate_items=[evidence.statement],
        missing_elements=[],
        explanation="La evidencia ficticia respalda coordinación multifuncional.",
        recommendation="Preparar un ejemplo verificable para entrevista.",
        confidence=0.9,
    )
    return JobCompatibility(
        job_index=index,
        job_title=title,
        company=company,
        compatibility_score=total,
        compatibility_band=compatibility_band_for_score(total),
        score_before_penalties=total,
        total_penalty=0.0,
        penalties=[],
        dimensions=dimensions,
        requirement_matches=[match],
        strengths=["Coordinación", "Comunicación ejecutiva"],
        critical_gaps=[],
        other_gaps=["Certificación PMP no respaldada"],
        risks=[],
        recommendations=["Personalizar ejemplos con evidencia real."],
        confidence=0.9,
        summary="Compatibilidad ficticia para validar serialización y UI.",
        covered_required_count=1,
        total_required_count=1,
        covered_preferred_count=0,
        total_preferred_count=0,
    )
