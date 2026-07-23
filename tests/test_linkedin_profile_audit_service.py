from __future__ import annotations

from schemas.enums import EvidenceStatus, PriorityLevel, SkillCategory
from schemas.profile_models import (
    ATSKeyword,
    AboutOutput,
    HeadlineOutput,
    PrioritizedSkill,
    RewrittenExperienceEntry,
)
from services.linkedin_profile_audit_service import audit_linkedin_profile_output
from tests.linkedin_profile_helpers import build_candidate_profile, build_linkedin_output, build_market_analysis


def test_valid_linkedin_profile_output_passes_audit():
    result = audit_linkedin_profile_output(build_linkedin_output(), build_candidate_profile(), build_market_analysis())

    assert result.passed
    assert result.findings == []


def test_headline_length_count_cliche_and_missing_keyword_are_audited():
    output = build_linkedin_output()
    output = output.model_copy(
        update={
            "headline": HeadlineOutput.model_construct(
                text="Project Manager results-driven con Kubernetes " + ("x" * 190),
                character_count=10,
                included_keywords=["Kubernetes"],
            )
        }
    )

    result = audit_linkedin_profile_output(output, build_candidate_profile(), build_market_analysis())

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "220" in messages
    assert "character_count" in messages
    assert "no esta respaldada" in messages
    assert any(finding.severity == "warning" and "results-driven" in finding.message for finding in result.findings)


def test_about_blocks_invented_tool_or_number():
    output = build_linkedin_output()
    about_text = output.about.text + " Soy especialista en Kubernetes y logre 99% de mejora."
    output = output.model_copy(
        update={
            "about": AboutOutput(
                text=about_text,
                character_count=len(about_text),
                included_keywords=output.about.included_keywords,
                claims_requiring_review=output.about.claims_requiring_review,
            )
        }
    )

    result = audit_linkedin_profile_output(output, build_candidate_profile(), build_market_analysis())

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "mercado no respaldada" in messages
    assert "99" in messages


def test_experience_correspondence_and_unsupported_claims_are_audited():
    output = build_linkedin_output()
    invalid_experience = RewrittenExperienceEntry(
        source_role_title="Director de Transformacion",
        suggested_role_title="Director de Transformacion",
        employer="Empresa Inventada",
        rewritten_text="Dirigi una transformacion Kubernetes con resultados no respaldados.",
        included_keywords=["Kubernetes"],
        unsupported_claims=["Dirigi transformacion Kubernetes"],
    )
    output = output.model_copy(update={"experience": [invalid_experience]})

    result = audit_linkedin_profile_output(output, build_candidate_profile(), build_market_analysis())

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "empleo fuente" in messages
    assert "unsupported_claims" in messages


def test_skill_ranking_duplicates_and_missing_skill_are_audited():
    output = build_linkedin_output()
    missing = PrioritizedSkill(
        name="Kubernetes",
        category=SkillCategory.TOOL,
        priority_rank=2,
        evidence_status=EvidenceStatus.MISSING,
        rationale="Brecha de mercado.",
        recommended_placement=["skills"],
    )
    output.prioritized_skills[1] = missing
    output.prioritized_skills[2].priority_rank = 2

    result = audit_linkedin_profile_output(output, build_candidate_profile(), build_market_analysis())

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "rankings" in messages
    assert "MISSING" in messages


def test_ats_keyword_support_frequency_sections_and_duplicates_are_audited():
    output = build_linkedin_output()
    output.ats_keywords.append(
        ATSKeyword(
            keyword="Kubernetes",
            normalized_keyword="kubernetes",
            priority=PriorityLevel.HIGH,
            frequency_in_jobs=2,
            supported_by_candidate=True,
            evidence_status=EvidenceStatus.SUPPORTED,
            recommended_sections=["headline"],
        )
    )

    result = audit_linkedin_profile_output(output, build_candidate_profile(), build_market_analysis())

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "duplicada" in messages
    assert "frecuencia" in messages
    assert "respaldo" in messages


def test_banner_template_sensitive_contact_and_market_only_tool_are_audited():
    output = build_linkedin_output()
    output.banner.primary_line = "Project Manager Kubernetes"
    output.banner.supporting_line = "correo demo@example.com"
    output.banner.recommended_template = "flashy_template"

    result = audit_linkedin_profile_output(output, build_candidate_profile(), build_market_analysis())

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "plantilla" in messages
    assert "sensibles" in messages or "telefono" in messages
    assert "mercado no respaldada" in messages
