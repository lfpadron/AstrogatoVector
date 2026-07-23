from __future__ import annotations

from datetime import datetime

from schemas.enums import EvidenceStatus, OutputLanguage
from schemas.targeted_cv_models import (
    TargetedCV,
    TargetedCVBullet,
    TargetedCVExperienceEntry,
    TargetedCVHeader,
    TargetedCVSkill,
    TargetedCVSummary,
)
from services.compatibility_scoring_service import CompatibilityScoringService
from tests.compatibility_helpers import build_compatibility_inputs


def build_targeted_cv_inputs():
    profile, market, evaluation = build_compatibility_inputs()
    compatibility = CompatibilityScoringService().calculate_report(evaluation, market, profile)
    return profile, market, compatibility


def build_targeted_cv(job_index: int = 1) -> TargetedCV:
    profile, market, compatibility = build_targeted_cv_inputs()
    job = next(item for item in market.job_analyses if item.job_index == job_index)
    job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == job_index)
    evidence = profile.leadership_capabilities[0]
    skills = [
        TargetedCVSkill(
            name="Agile",
            category="business",
            priority=1,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_evidence=[evidence],
            used_in_sections=["summary", "experience", "skills"],
        ),
        TargetedCVSkill(
            name="Stakeholder management",
            category="communication",
            priority=2,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_evidence=[evidence],
            used_in_sections=["summary", "experience", "skills"],
        ),
        TargetedCVSkill(
            name="Jira",
            category="tool",
            priority=3,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_evidence=[evidence],
            used_in_sections=["experience", "skills"],
        ),
    ]
    employment = profile.employment_history[0]
    summary_text = (
        "Project Manager con experiencia respaldada en gestión de proyectos Agile, coordinación de stakeholders "
        "y seguimiento operativo con Jira. Su trayectoria muestra colaboración con equipos de tecnología, "
        "control de prioridades y mejora de tiempos de seguimiento de 15%, alineando ejecución y comunicación "
        "para vacantes que requieren liderazgo práctico en proyectos digitales."
    )
    return TargetedCV(
        output_language=OutputLanguage.ES,
        generated_at=datetime(2026, 1, 1),
        target_job_index=job.job_index,
        target_job_title=job.title,
        target_company=job.company,
        header=TargetedCVHeader(
            candidate_name=None,
            professional_title="Project Manager",
            target_role_title=job.title,
            location=None,
        ),
        summary=TargetedCVSummary(
            text=summary_text,
            included_keywords=["Agile", "Stakeholder management", "Jira"],
            evidence_items=[evidence],
        ),
        skills=skills,
        experience=[
            TargetedCVExperienceEntry(
                source_role_title=employment.role_title,
                display_role_title=employment.role_title,
                employer=employment.employer,
                start_date=employment.start_date,
                end_date=employment.end_date,
                is_current=employment.is_current,
                location=employment.location,
                included=True,
                bullets=[
                    TargetedCVBullet(
                        text=(
                            "Gestionó proyectos Agile con coordinación de stakeholders, seguimiento en Jira "
                            "y comunicación operativa entre equipos de tecnología."
                        ),
                        evidence_items=[evidence],
                        included_keywords=["Agile", "Stakeholder management", "Jira"],
                    ),
                    TargetedCVBullet(
                        text="Redujo tiempos de seguimiento 15% en proyectos internos con control de prioridades.",
                        evidence_items=[evidence],
                        included_keywords=["Jira"],
                    ),
                ],
                technologies=["Jira"],
                industries=employment.industries,
            )
        ],
        ats_keywords_used=["Agile", "Stakeholder management", "Jira"],
        ats_keywords_missing=[gap for gap in job_compatibility.critical_gaps],
        ats_keywords_omitted=["Kubernetes"] if job_index == 2 else [],
        overall_review_notes=["Fixture ficticia para pruebas automatizadas."],
    )
