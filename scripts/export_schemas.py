"""Export JSON Schema files for Astrogato Vector structured contracts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.audit_models import AuditReport  # noqa: E402
from schemas.banner_models import BannerAuditResult, BannerRenderInput, BannerRenderResult  # noqa: E402
from schemas.communication_models import CommunicationOutput  # noqa: E402
from schemas.compatibility_models import CompatibilityReport  # noqa: E402
from schemas.content_models import FourWeekContentPlan  # noqa: E402
from schemas.deliverable_models import FinalDeliverablePackage, FinalPackageBuildResult  # noqa: E402
from schemas.evidence_models import CandidateProfessionalProfile  # noqa: E402
from schemas.extraction_models import CandidateExtractionResult, EvidenceAuditResult, PrivacyFilterResult  # noqa: E402
from schemas.input_models import CandidateInput  # noqa: E402
from schemas.job_analysis_models import JobAnalysisResult, JobAnalysisAuditResult  # noqa: E402
from schemas.market_models import TargetMarketAnalysis  # noqa: E402
from schemas.profile_models import LinkedInProfileOutput  # noqa: E402
from schemas.profile_generation_models import LinkedInProfileGenerationResult, LinkedInProfileAuditResult  # noqa: E402
from schemas.result_models import ApplicationResult  # noqa: E402
from schemas.schema_utils import export_model_json_schema  # noqa: E402
from schemas.targeted_cv_models import (  # noqa: E402
    TargetedCV,
    TargetedCVATSAudit,
    TargetedCVAuditResult,
    TargetedCVEditableValidationResult,
    TargetedCVGenerationResult,
)

OUTPUT_DIR = PROJECT_ROOT / "generated_schemas"
MODELS = [
    CandidateInput,
    CandidateProfessionalProfile,
    CandidateExtractionResult,
    EvidenceAuditResult,
    PrivacyFilterResult,
    JobAnalysisResult,
    JobAnalysisAuditResult,
    TargetMarketAnalysis,
    LinkedInProfileOutput,
    LinkedInProfileGenerationResult,
    LinkedInProfileAuditResult,
    BannerRenderInput,
    BannerRenderResult,
    BannerAuditResult,
    CompatibilityReport,
    AuditReport,
    FinalDeliverablePackage,
    FinalPackageBuildResult,
    TargetedCV,
    TargetedCVGenerationResult,
    TargetedCVAuditResult,
    TargetedCVATSAudit,
    TargetedCVEditableValidationResult,
    CommunicationOutput,
    FourWeekContentPlan,
    ApplicationResult,
]


def main() -> None:
    """Export all configured schemas."""
    for model_class in MODELS:
        output_path = OUTPUT_DIR / f"{model_class.__name__}.schema.json"
        export_model_json_schema(model_class, output_path)
        print(output_path)


if __name__ == "__main__":
    main()
