"""Controlled values used by Astrogato Vector data contracts."""

from __future__ import annotations

from enum import Enum


class OutputLanguage(str, Enum):
    """Supported output languages."""

    ES = "es"
    EN = "en"


class ContentSource(str, Enum):
    """Origin of normalized user or generated content."""

    TEXT = "text"
    DOCX = "docx"
    PDF = "pdf"
    URL = "url"
    GENERATED = "generated"


class EvidenceStatus(str, Enum):
    """Evidence strength assigned to a professional claim."""

    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"


class PriorityLevel(str, Enum):
    """Priority used for gaps, keywords and actions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SeniorityLevel(str, Enum):
    """Normalized seniority level."""

    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    UNSPECIFIED = "unspecified"


class SkillCategory(str, Enum):
    """Skill or keyword category."""

    TECHNICAL = "technical"
    LEADERSHIP = "leadership"
    BUSINESS = "business"
    COMMUNICATION = "communication"
    STRATEGY = "strategy"
    INDUSTRY = "industry"
    LANGUAGE = "language"
    TOOL = "tool"


class RequirementMatchStatus(str, Enum):
    """Candidate status against a specific job requirement."""

    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_DEMONSTRATED = "not_demonstrated"
    CONFLICT = "conflict"


class RequirementCoverage(str, Enum):
    """Semantic coverage of a candidate against one job requirement."""

    FULL = "full"
    PARTIAL = "partial"
    INDIRECT = "indirect"
    MISSING = "missing"
    CONFLICT = "conflict"
    NOT_APPLICABLE = "not_applicable"


class CompatibilityBand(str, Enum):
    """Human-readable compatibility band."""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class AuditSeverity(str, Enum):
    """Severity of a positioning or ATS audit finding."""

    PASS = "pass"
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    WARNING = "warning"
    CRITICAL = "critical"


class CompatibilityDimensionName(str, Enum):
    """Required score dimensions for job compatibility."""

    EXPERIENCE_RESPONSIBILITIES = "experience_responsibilities"
    SKILLS_KNOWLEDGE = "skills_knowledge"
    TOOLS_TECHNOLOGIES = "tools_technologies"
    LEADERSHIP_MANAGEMENT = "leadership_management"
    INDUSTRY_BUSINESS = "industry_business"
    EDUCATION_CERTIFICATIONS_LANGUAGES = "education_certifications_languages"


class ProfessionalMessageType(str, Enum):
    """Professional outreach message variants."""

    CONNECTION_REQUEST = "connection_request"
    POST_ACCEPTANCE = "post_acceptance"
    VACANCY_CONTACT = "vacancy_contact"
    FOLLOW_UP = "follow_up"
