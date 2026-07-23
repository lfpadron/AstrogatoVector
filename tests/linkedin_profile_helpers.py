from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr

from schemas.enums import EvidenceStatus, PriorityLevel, SeniorityLevel, SkillCategory
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
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
from services.openai_config import OpenAISettings


@dataclass
class FakeUsage:
    input_tokens: int = 300
    output_tokens: int = 220
    total_tokens: int = 520


class FakeSDKResponse:
    def __init__(self, output_parsed=None, model: str = "quality-model", usage=None) -> None:
        self.output_parsed = output_parsed
        self._request_id = "req_linkedin"
        self.model = model
        self.usage = usage or FakeUsage()


class FakeResponses:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeClient:
    def __init__(self, result) -> None:
        self.responses = FakeResponses(result)


def fake_settings() -> OpenAISettings:
    return OpenAISettings(
        api_key=SecretStr("unit-test-secret"),
        model_fast="fast-model",
        model_quality="quality-model",
        timeout_seconds=30,
        max_retries=1,
        diagnostic_enabled=True,
    )


def prompt_loader(filename: str) -> str:
    prompts = {
        "system_guardrails.txt": "Sistema: evidencia CandidateProfessionalProfile y mercado TargetMarketAnalysis.",
        "generate_profile.txt": "Genera LinkedInProfileOutput sin inventar capacidades.",
    }
    return prompts[filename]


def build_candidate_profile() -> CandidateProfessionalProfile:
    reference = EvidenceReference(
        source_section="CV - Experiencia",
        source_excerpt="Project Manager gestiono proyectos Agile, Jira, stakeholders y redujo tiempos 15%.",
    )
    responsibility = EvidenceItem(
        statement="Gestiono proyectos Agile con stakeholders y seguimiento en Jira.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.9,
        references=[reference],
    )
    achievement = Achievement(
        description="Redujo tiempos de seguimiento 15% en proyectos internos.",
        measurable_result="15%",
        evidence_status=EvidenceStatus.SUPPORTED,
        references=[reference],
    )
    agile = CandidateSkill(
        name="Agile",
        normalized_name="agile",
        category=SkillCategory.BUSINESS,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.93,
        references=[reference],
    )
    stakeholders = CandidateSkill(
        name="Stakeholder management",
        normalized_name="stakeholder management",
        category=SkillCategory.COMMUNICATION,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.9,
        references=[reference],
    )
    jira = CandidateSkill(
        name="Jira",
        normalized_name="jira",
        category=SkillCategory.TOOL,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.88,
        references=[reference],
    )
    employment = EmploymentEntry(
        employer="Empresa Demo",
        role_title="Project Manager",
        start_date="2020",
        end_date="2025",
        responsibilities=[responsibility],
        achievements=[achievement],
        technologies=[jira],
        industries=["Tecnologia"],
    )
    return CandidateProfessionalProfile(
        professional_identity="Project Manager",
        targetable_roles=["Project Manager", "Program Manager"],
        summary="Project Manager con evidencia en Agile, Jira, stakeholders y gestion de proyectos.",
        total_years_experience=None,
        seniority=SeniorityLevel.MANAGER,
        industries=["Tecnologia"],
        employment_history=[employment],
        skills=[agile, stakeholders, jira],
        leadership_capabilities=[responsibility],
        achievements=[achievement],
        missing_information=["Validar metricas adicionales antes de publicar."],
    )


def build_market_analysis() -> TargetMarketAnalysis:
    agile_req = JobRequirement(
        name="Agile",
        normalized_name="agile",
        category=SkillCategory.BUSINESS,
        description="Experiencia con Agile.",
        required=True,
        importance=PriorityLevel.HIGH,
        exact_keywords=["Agile"],
    )
    stakeholder_req = JobRequirement(
        name="Stakeholder management",
        normalized_name="stakeholder management",
        category=SkillCategory.COMMUNICATION,
        description="Gestion de stakeholders.",
        required=True,
        importance=PriorityLevel.HIGH,
        exact_keywords=["stakeholders"],
    )
    analyses = [
        JobAnalysis(
            job_index=1,
            title="Project Manager",
            company="Empresa Uno",
            inferred_seniority=SeniorityLevel.MANAGER,
            role_summary="Rol de gestion de proyectos Agile y stakeholders.",
            responsibilities=["gestionar proyectos Agile"],
            requirements=[agile_req, stakeholder_req],
            tools_and_technologies=["Jira"],
            exact_keywords=["Agile", "Jira"],
        ),
        JobAnalysis(
            job_index=2,
            title="Program Manager",
            company="Empresa Dos",
            inferred_seniority=SeniorityLevel.MANAGER,
            role_summary="Rol de programas con stakeholders y posibles plataformas Kubernetes.",
            responsibilities=["coordinar stakeholders"],
            requirements=[stakeholder_req],
            tools_and_technologies=["Kubernetes"],
            exact_keywords=["stakeholders", "Kubernetes"],
        ),
    ]
    return TargetMarketAnalysis(
        target_role_family="Gestion de proyectos tecnologicos",
        suggested_target_titles=["Project Manager", "Program Manager"],
        dominant_seniority=SeniorityLevel.MANAGER,
        market_summary="Mercado ficticio orientado a Agile, stakeholders, Jira y Kubernetes.",
        common_responsibilities=["gestionar proyectos Agile"],
        common_requirements=[agile_req, stakeholder_req],
        keywords=[
            MarketKeyword(
                keyword="Agile",
                normalized_keyword="agile",
                frequency=2,
                job_indices=[1, 2],
                category=SkillCategory.BUSINESS,
                priority=PriorityLevel.HIGH,
            ),
            MarketKeyword(
                keyword="Stakeholder management",
                normalized_keyword="stakeholder management",
                frequency=2,
                job_indices=[1, 2],
                category=SkillCategory.COMMUNICATION,
                priority=PriorityLevel.HIGH,
            ),
            MarketKeyword(
                keyword="Jira",
                normalized_keyword="jira",
                frequency=1,
                job_indices=[1],
                category=SkillCategory.TOOL,
                priority=PriorityLevel.MEDIUM,
            ),
            MarketKeyword(
                keyword="Kubernetes",
                normalized_keyword="kubernetes",
                frequency=1,
                job_indices=[2],
                category=SkillCategory.TOOL,
                priority=PriorityLevel.HIGH,
            ),
        ],
        business_skills=["Agile"],
        leadership_skills=["Stakeholder management"],
        tools_and_technologies=["Jira", "Kubernetes"],
        industries=["Tecnologia"],
        differentiators=["Kubernetes como brecha de mercado"],
        job_analyses=analyses,
    )


def build_linkedin_output() -> LinkedInProfileOutput:
    headline = "Project Manager | Agile, Jira y stakeholder management"
    about = (
        "Soy Project Manager con experiencia respaldada en gestion de proyectos Agile, Jira y stakeholder "
        "management. He coordinado iniciativas con stakeholders, seguimiento operativo y comunicacion clara "
        "para mantener prioridades visibles entre equipos de tecnologia. En Empresa Demo gestione proyectos "
        "internos y reduje tiempos de seguimiento 15%, siempre con foco en evidencia verificable y colaboracion."
    )
    rewritten = (
        "Gestione proyectos Agile en Empresa Demo, coordinando stakeholder management, seguimiento en Jira y comunicacion "
        "operativa entre equipos de tecnologia. El trabajo incluyo control de prioridades y una reduccion de "
        "tiempos de seguimiento 15% respaldada por la evidencia del perfil."
    )
    return LinkedInProfileOutput(
        banner=BannerContent(
            primary_line="Project Manager para proyectos Agile",
            specialty_line="Agile, Jira, stakeholder management",
            supporting_line="Gestion de proyectos tecnologicos",
            visual_concept="Banner sobrio con estructura limpia y bloques de proyecto.",
            recommended_template="professional_light",
        ),
        headline=HeadlineOutput(
            text=headline,
            character_count=len(headline),
            included_keywords=["Agile", "Jira", "Stakeholder management"],
        ),
        about=AboutOutput(
            text=about,
            character_count=len(about),
            included_keywords=["Agile", "Jira", "Stakeholder management"],
            claims_requiring_review=[],
        ),
        experience=[
            RewrittenExperienceEntry(
                source_role_title="Project Manager",
                suggested_role_title="Project Manager",
                employer="Empresa Demo",
                rewritten_text=rewritten,
                included_keywords=["Agile", "Jira", "Stakeholder management"],
            )
        ],
        prioritized_skills=[
            PrioritizedSkill(
                name="Agile",
                category=SkillCategory.BUSINESS,
                priority_rank=1,
                evidence_status=EvidenceStatus.SUPPORTED,
                rationale="Respaldada por el perfil y frecuente en el mercado.",
                recommended_placement=["headline", "about", "skills"],
            ),
            PrioritizedSkill(
                name="Stakeholder management",
                category=SkillCategory.COMMUNICATION,
                priority_rank=2,
                evidence_status=EvidenceStatus.SUPPORTED,
                rationale="Respaldada por experiencia y recurrente en vacantes.",
                recommended_placement=["headline", "experience", "skills"],
            ),
            PrioritizedSkill(
                name="Jira",
                category=SkillCategory.TOOL,
                priority_rank=3,
                evidence_status=EvidenceStatus.SUPPORTED,
                rationale="Herramienta respaldada por la experiencia.",
                recommended_placement=["about", "experience", "skills"],
            ),
        ],
        ats_keywords=[
            ATSKeyword(
                keyword="Agile",
                normalized_keyword="agile",
                priority=PriorityLevel.HIGH,
                frequency_in_jobs=2,
                supported_by_candidate=True,
                evidence_status=EvidenceStatus.SUPPORTED,
                recommended_sections=["headline", "about", "experience"],
            ),
            ATSKeyword(
                keyword="Stakeholder management",
                normalized_keyword="stakeholder management",
                priority=PriorityLevel.HIGH,
                frequency_in_jobs=2,
                supported_by_candidate=True,
                evidence_status=EvidenceStatus.SUPPORTED,
                recommended_sections=["headline", "about", "experience"],
            ),
            ATSKeyword(
                keyword="Kubernetes",
                normalized_keyword="kubernetes",
                priority=PriorityLevel.HIGH,
                frequency_in_jobs=1,
                supported_by_candidate=False,
                evidence_status=EvidenceStatus.MISSING,
                recommended_sections=[],
            ),
        ],
        global_review_notes=["Kubernetes aparece como brecha de mercado y no debe agregarse como capacidad."],
    )
