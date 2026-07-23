from __future__ import annotations

from schemas.compatibility_models import CompatibilityReport
from schemas.enums import OutputLanguage
from schemas.examples import (
    build_example_audit_report,
    build_example_compatibility_report,
    build_example_linkedin_profile,
    build_example_market_analysis,
    build_example_professional_profile,
)
from services.final_package_service import FinalPackageService


def test_final_package_builds_from_audited_content_without_banner():
    result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        build_example_linkedin_profile(),
        build_example_compatibility_report(),
        build_example_audit_report(),
        OutputLanguage.ES,
        banner_available=False,
    )

    assert result.success
    assert result.package is not None
    assert result.package.content_source == "generated-and-audited"
    assert result.package.banner_included is False
    assert "Banner PNG not included." in result.warnings
    assert "LinkedIn" in result.package.executive_summary


def test_final_package_prioritizes_user_edited_content():
    linkedin = build_example_linkedin_profile()
    edit_state = {
        "edited": True,
        "banner": {
            "primary_line": "Línea editada",
            "specialty_line": "Especialidad editada",
            "supporting_line": "Apoyo editado",
        },
        "headline": "Headline editado con foco en proyectos digitales",
        "about": linkedin.about.text,
        "experience": [{"suggested_role_title": "Rol editado", "rewritten_text": linkedin.experience[0].rewritten_text}],
        "selected_skills": ["Gestión de proyectos"],
        "selected_keywords": ["Stakeholder management"],
    }

    result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        linkedin,
        build_example_compatibility_report(),
        build_example_audit_report(),
        "es",
        edit_state=edit_state,
    )

    assert result.success
    assert result.package is not None
    assert result.package.content_source == "user-edited"
    assert result.package.headline == "Headline editado con foco en proyectos digitales"
    assert result.package.banner_primary_line == "Línea editada"
    assert result.package.experiences[0].suggested_role_title == "Rol editado"
    assert [skill.name for skill in result.package.prioritized_skills] == ["Gestión de proyectos"]


def test_final_package_blocks_missing_audit():
    audit = build_example_audit_report().model_copy(update={"success": False, "linkedin_positioning": None, "ats_estimation": None})
    result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        build_example_linkedin_profile(),
        build_example_compatibility_report(),
        audit,
        OutputLanguage.ES,
    )

    assert not result.success
    assert result.error_category == "missing_final_audit"
    assert "auditoría integral" in (result.user_message or "")


def test_final_package_supports_english_and_six_jobs():
    compatibility = _six_job_report()
    result = FinalPackageService().build_package(
        build_example_professional_profile(),
        build_example_market_analysis(),
        build_example_linkedin_profile(),
        compatibility,
        build_example_audit_report(),
        OutputLanguage.EN,
        banner_available=True,
        banner_fingerprint="banner",
    )

    assert result.success
    assert result.package is not None
    assert result.package.output_language == "en"
    assert len(result.package.compatibility_report.job_compatibilities) == 6
    assert result.package.banner_included is True
    assert result.package.package_version == "1.0"


def _six_job_report() -> CompatibilityReport:
    base = build_example_compatibility_report()
    jobs = []
    for index in range(1, 7):
        source = base.job_compatibilities[(index - 1) % 2]
        jobs.append(source.model_copy(deep=True, update={"job_index": index, "job_title": f"Vacante {index}"}))
    average = round(sum(job.compatibility_score for job in jobs) / len(jobs), 1)
    highest = max(jobs, key=lambda job: (job.compatibility_score, -job.job_index)).job_index
    return CompatibilityReport(
        job_compatibilities=jobs,
        highest_compatibility_job_index=highest,
        average_compatibility_score=average,
        common_strengths=base.common_strengths,
        common_gaps=base.common_gaps,
        strategic_recommendations=base.strategic_recommendations,
        methodology_version=base.methodology_version,
        disclaimer=base.disclaimer,
    )
