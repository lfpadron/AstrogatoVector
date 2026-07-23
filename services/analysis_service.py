"""Contracts for future candidate, market and output analysis stages."""

from __future__ import annotations

from schemas.audit_models import AuditReport
from schemas.communication_models import CommunicationOutput
from schemas.compatibility_models import CompatibilityReport
from schemas.content_models import FourWeekContentPlan
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput, JobInput
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_models import LinkedInProfileOutput
from schemas.result_models import ApplicationResult
from services.candidate_extraction_service import CandidateExtractionService
from services.compatibility_service import CompatibilityService
from services.final_audit_service import FinalAuditService
from services.job_analysis_service import JobAnalysisService
from services.linkedin_profile_generation_service import LinkedInProfileGenerationService
from services.openai_service import OpenAIService, create_openai_service


def analyze_candidate_positioning(candidate_text: str, job_texts: list[str]) -> dict:
    """Analyze the candidate against target jobs in a later increment."""
    raise NotImplementedError("Se implementará en un incremento posterior.")


def extract_candidate_professional_profile(
    candidate_input: CandidateInput,
    openai_service: OpenAIService | None = None,
) -> CandidateProfessionalProfile:
    """Stage 1: extract an evidence-based candidate profile."""
    service = CandidateExtractionService(openai_service or create_openai_service())
    result = service.extract_candidate_profile(candidate_input)
    if not result.success or result.profile is None:
        raise RuntimeError(result.user_message or "No fue posible extraer el perfil profesional.")
    return result.profile


def analyze_target_market(
    candidate_profile: CandidateProfessionalProfile,
    jobs: list[JobInput],
) -> TargetMarketAnalysis:
    """Stage 2: analyze target jobs and consolidate the market without candidate data."""
    _ = candidate_profile
    service = JobAnalysisService(create_openai_service())
    result = service.analyze_jobs(jobs, OutputLanguage.ES)
    if not result.success or result.market_analysis is None:
        raise RuntimeError(result.user_message or "No fue posible analizar las vacantes objetivo.")
    return result.market_analysis


def generate_linkedin_profile(
    candidate_profile: CandidateProfessionalProfile,
    target_market: TargetMarketAnalysis,
    output_language: OutputLanguage = OutputLanguage.ES,
    openai_service: OpenAIService | None = None,
) -> LinkedInProfileOutput:
    """Stage 3: generate LinkedIn profile text and banner copy."""
    service = LinkedInProfileGenerationService(openai_service or create_openai_service())
    result = service.generate_profile(candidate_profile, target_market, output_language)
    if not result.success or result.profile_output is None:
        raise RuntimeError(result.user_message or "No fue posible generar el perfil de LinkedIn.")
    return result.profile_output


def score_compatibility(
    candidate_profile: CandidateProfessionalProfile,
    target_market: TargetMarketAnalysis,
    output_language: OutputLanguage = OutputLanguage.ES,
    openai_service: OpenAIService | None = None,
) -> CompatibilityReport:
    """Stage 4: calculate explainable compatibility per target job."""
    service = CompatibilityService(openai_service or create_openai_service())
    result = service.analyze_compatibility(candidate_profile, target_market, output_language)
    if not result.success or result.compatibility_report is None:
        raise RuntimeError(result.user_message or "No fue posible calcular la compatibilidad.")
    return result.compatibility_report


def audit_positioning(
    candidate_profile: CandidateProfessionalProfile,
    target_market: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    compatibility: CompatibilityReport,
) -> AuditReport:
    """Stage 5: produce local LinkedIn and ATS audit outputs."""
    return FinalAuditService().generate_report(
        candidate_profile,
        target_market,
        linkedin_profile,
        compatibility,
    )


def generate_professional_communications(
    candidate_profile: CandidateProfessionalProfile,
    target_market: TargetMarketAnalysis,
) -> CommunicationOutput:
    """Future stage 6: draft headhunter messages and cover letters."""
    raise NotImplementedError("Se implementará en un incremento posterior.")


def generate_four_week_content_plan(
    candidate_profile: CandidateProfessionalProfile,
    target_market: TargetMarketAnalysis,
) -> FourWeekContentPlan:
    """Future stage 7: draft a four-week LinkedIn content plan."""
    raise NotImplementedError("Se implementará en un incremento posterior.")


def build_application_result(
    output_language: OutputLanguage,
    candidate_profile: CandidateProfessionalProfile,
    target_market: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    compatibility: CompatibilityReport,
    audits: AuditReport,
    communication: CommunicationOutput,
    content_plan: FourWeekContentPlan,
) -> ApplicationResult:
    """Future aggregation stage: build the complete application result."""
    raise NotImplementedError("Se implementará en un incremento posterior.")
