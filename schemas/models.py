"""Compatibility facade for Astrogato Vector schema models."""

from schemas.audit_models import (
    ATSAudit,
    AuditFinding,
    AuditRecommendation,
    AuditReport,
    AuditScoreComponent,
    FinalAuditValidationFinding,
    FinalAuditValidationResult,
    LinkedInPositioningAudit,
)
from schemas.banner_models import BannerAuditResult, BannerRenderInput, BannerRenderResult, BannerTemplate, BannerTextBox
from schemas.communication_models import CommunicationOutput, CoverLetter, ProfessionalMessage
from schemas.compatibility_models import (
    CompatibilityDimension,
    CompatibilityPenalty,
    CompatibilityReport,
    JobCompatibility,
    RequirementMatch,
)
from schemas.compatibility_analysis_models import (
    CompatibilityAnalysisResult,
    CompatibilityAuditFinding,
    CompatibilityAuditResult,
    CompatibilitySemanticEvaluation,
    JobCompatibilitySemanticEvaluation,
    SemanticRequirementMatch,
)
from schemas.content_models import FourWeekContentPlan, LinkedInPostSuggestion
from schemas.deliverable_models import ExportAuditResult, FinalDeliverablePackage, FinalPackageBuildResult
from schemas.diagnostic_models import DiagnosticCapability, OpenAIDiagnosticResponse, OpenAIDiagnosticResult
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.extraction_models import (
    CandidateExtractionResult,
    EvidenceAuditFinding,
    EvidenceAuditResult,
    PrivacyFilterResult,
)
from schemas.input_models import (
    CandidateInput,
    DocumentParseResult,
    DocumentParseSummary,
    JobInput,
    LinkReadResult,
    LinkReadSummary,
)
from schemas.job_analysis_models import JobAnalysisAuditFinding, JobAnalysisAuditResult, JobAnalysisResult
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
from schemas.profile_generation_models import (
    LinkedInProfileAuditFinding,
    LinkedInProfileAuditResult,
    LinkedInProfileGenerationResult,
)
from schemas.result_models import ApplicationResult

__all__ = [
    "ATSAudit",
    "ATSKeyword",
    "AboutOutput",
    "Achievement",
    "ApplicationResult",
    "AuditFinding",
    "AuditRecommendation",
    "AuditReport",
    "AuditScoreComponent",
    "BannerContent",
    "BannerAuditResult",
    "BannerRenderInput",
    "BannerRenderResult",
    "BannerTemplate",
    "BannerTextBox",
    "CandidateInput",
    "CandidateExtractionResult",
    "CandidateProfessionalProfile",
    "CandidateSkill",
    "CommunicationOutput",
    "CompatibilityAnalysisResult",
    "CompatibilityAuditFinding",
    "CompatibilityAuditResult",
    "CompatibilityDimension",
    "CompatibilityPenalty",
    "CompatibilityReport",
    "CompatibilitySemanticEvaluation",
    "CoverLetter",
    "DiagnosticCapability",
    "DocumentParseResult",
    "DocumentParseSummary",
    "EmploymentEntry",
    "EvidenceItem",
    "EvidenceReference",
    "EvidenceAuditFinding",
    "EvidenceAuditResult",
    "ExportAuditResult",
    "FinalAuditValidationFinding",
    "FinalAuditValidationResult",
    "FinalDeliverablePackage",
    "FinalPackageBuildResult",
    "FourWeekContentPlan",
    "HeadlineOutput",
    "JobAnalysis",
    "JobAnalysisAuditFinding",
    "JobAnalysisAuditResult",
    "JobAnalysisResult",
    "JobCompatibility",
    "JobCompatibilitySemanticEvaluation",
    "JobInput",
    "JobRequirement",
    "LinkedInPositioningAudit",
    "LinkedInProfileAuditFinding",
    "LinkedInProfileAuditResult",
    "LinkedInProfileGenerationResult",
    "LinkedInPostSuggestion",
    "LinkedInProfileOutput",
    "LinkReadResult",
    "LinkReadSummary",
    "MarketKeyword",
    "OpenAIDiagnosticResponse",
    "OpenAIDiagnosticResult",
    "PrioritizedSkill",
    "ProfessionalMessage",
    "PrivacyFilterResult",
    "RequirementMatch",
    "SemanticRequirementMatch",
    "RewrittenExperienceEntry",
    "TargetMarketAnalysis",
]
