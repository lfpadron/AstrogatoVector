"""Models for the final professional deliverable package."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.audit_models import AuditReport
from schemas.base import StrictBaseModel
from schemas.compatibility_models import CompatibilityReport
from schemas.enums import OutputLanguage
from schemas.profile_models import ATSKeyword, PrioritizedSkill, RewrittenExperienceEntry

FINAL_PACKAGE_VERSION = "1.0"
FINAL_PACKAGE_EXPORT_VERSION = "1.0"
MAX_INDIVIDUAL_EXPORT_SIZE_MB = 15
MAX_FINAL_ZIP_SIZE_MB = 40

CONTENT_SOURCE_USER_EDITED = "user-edited"
CONTENT_SOURCE_GENERATED_AUDITED = "generated-and-audited"
ContentSourceLabel = Literal["user-edited", "generated-and-audited"]

FINAL_PACKAGE_REQUIRED_SECTIONS = (
    "Portada",
    "Resumen ejecutivo",
    "Perfil de LinkedIn",
    "Banner textual",
    "Headline",
    "About",
    "Experiencia profesional",
    "Skills priorizadas",
    "Keywords ATS",
    "Compatibilidad por vacante",
    "Fortalezas",
    "Brechas",
    "Recomendaciones",
    "Auditoría LinkedIn",
    "Auditoría ATS",
    "Metodología y disclaimer",
)

FINAL_PACKAGE_DISCLAIMERS = {
    OutputLanguage.ES.value: (
        "Este paquete es orientativo y requiere revisión humana. Los scores no garantizan entrevistas, "
        "ranking, compatibilidad con un ATS específico ni contratación. No presentes keywords faltantes "
        "como experiencia real si no cuentas con evidencia."
    ),
    OutputLanguage.EN.value: (
        "This package is advisory and requires human review. Scores do not guarantee interviews, ranking, "
        "compatibility with any specific ATS, or hiring outcomes. Do not present missing keywords as real "
        "experience unless you have evidence."
    ),
}


class FinalDeliverablePackage(StrictBaseModel):
    """Serializable package content. Binary files are handled separately."""

    package_title: str = Field(min_length=1, max_length=180)
    output_language: OutputLanguage
    professional_identity: str = Field(min_length=1, max_length=300)
    target_roles: list[str] = Field(default_factory=list)
    headline: str = Field(min_length=1, max_length=220)
    about: str = Field(min_length=1, max_length=3000)
    banner_primary_line: str = Field(min_length=1, max_length=120)
    banner_specialty_line: str = Field(min_length=1, max_length=200)
    banner_supporting_line: str | None = Field(default=None, max_length=200)
    experiences: list[RewrittenExperienceEntry] = Field(default_factory=list)
    prioritized_skills: list[PrioritizedSkill] = Field(default_factory=list)
    ats_keywords: list[ATSKeyword] = Field(default_factory=list)
    compatibility_report: CompatibilityReport
    audit_report: AuditReport
    executive_summary: str = Field(min_length=1, max_length=3000)
    key_strengths: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)
    strategic_recommendations: list[str] = Field(default_factory=list)
    banner_included: bool = False
    content_source: ContentSourceLabel
    generated_at: datetime
    package_version: str = FINAL_PACKAGE_VERSION


class FinalPackageBuildResult(StrictBaseModel):
    """Result of package consolidation and validation."""

    success: bool
    package: FinalDeliverablePackage | None = None
    validation_passed: bool = False
    findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    package_fingerprint: str | None = None
    error_category: str | None = None
    user_message: str | None = None


class ExportAuditResult(StrictBaseModel):
    """Validation result for generated export bytes."""

    passed: bool
    findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
