from __future__ import annotations

import pytest

from schemas.enums import EvidenceStatus, SeniorityLevel, SkillCategory
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from services.evidence_audit_service import audit_candidate_profile_evidence

SOURCE = """
María Ejemplo

Empresa Demostración
Senior Project Manager
2018-2025

Responsable de coordinar proyectos de transformación digital, gestionar riesgos y colaborar
con equipos de tecnología y negocio.

Lideró la implementación de una nueva plataforma interna entregada dentro del calendario aprobado.
Mejoró la entrega en 20%.

Educación:
Maestría en Administración de Tecnologías.

Idiomas:
Español nativo.
Inglés intermedio.
"""


def test_supported_excerpt_present_passes_with_spacing_tolerance():
    profile = _profile(
        skill_reference=EvidenceReference(
            source_section="CV - Experiencia",
            source_excerpt="Responsable de coordinar proyectos de transformación digital, gestionar riesgos",
        )
    )

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert result.passed


def test_supported_excerpt_absent_blocks_result():
    profile = _profile(
        skill_reference=EvidenceReference(
            source_section="CV - Experiencia",
            source_excerpt="Dirigió una oficina global con presupuesto millonario",
        )
    )

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert not result.passed
    assert any("no pudo localizarse" in finding.message for finding in result.findings)


def test_duplicate_normalized_skill_blocks_result():
    profile = _profile()
    duplicate = profile.skills[0].model_copy(update={"name": "Project Mgmt.", "normalized_name": "gestión de proyectos"})
    profile.skills.append(duplicate)

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert not result.passed
    assert any("habilidad duplicada" in finding.message for finding in result.findings)


def test_duplicate_employment_blocks_result():
    profile = _profile()
    profile.employment_history.append(profile.employment_history[0])

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert not result.passed
    assert any("empleo duplicado" in finding.message for finding in result.findings)


def test_invented_percentage_blocks_result():
    profile = _profile(
        achievement=Achievement(
            description="Mejoró la entrega en 45%.",
            measurable_result="45%",
            evidence_status=EvidenceStatus.SUPPORTED,
            references=[_reference("Lideró la implementación de una nueva plataforma interna")],
        )
    )

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert not result.passed
    assert any("45%" in finding.message for finding in result.findings)


def test_supported_low_confidence_warning_and_error():
    profile = _profile()
    profile.skills[0].confidence = 0.65

    warning_result = audit_candidate_profile_evidence(profile, SOURCE)
    assert warning_result.passed
    assert any(finding.severity == "warning" for finding in warning_result.findings)

    profile.skills[0].confidence = 0.40
    error_result = audit_candidate_profile_evidence(profile, SOURCE)
    assert not error_result.passed
    assert any("confidence menor a 0.50" in finding.message for finding in error_result.findings)


def test_missing_skill_with_years_blocks_result():
    profile = _profile()
    profile.skills[0].evidence_status = EvidenceStatus.MISSING
    profile.skills[0].years_experience = 3

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert not result.passed
    assert any("MISSING" in finding.message for finding in result.findings)


def test_absurd_total_years_blocks_result():
    profile = _profile()
    profile.total_years_experience = 80

    result = audit_candidate_profile_evidence(profile, SOURCE)

    assert not result.passed
    assert any("rango razonable" in finding.message for finding in result.findings)


def test_conflict_without_notes_is_blocked_by_pydantic():
    with pytest.raises(ValueError):
        EvidenceItem(
            statement="El cargo difiere entre fuentes.",
            status=EvidenceStatus.CONFLICT,
            category=SkillCategory.BUSINESS,
            confidence=0.8,
            references=[],
        )


def _profile(
    *,
    skill_reference: EvidenceReference | None = None,
    achievement: Achievement | None = None,
) -> CandidateProfessionalProfile:
    reference = skill_reference or _reference(
        "Responsable de coordinar proyectos de transformación digital, gestionar riesgos"
    )
    skill = CandidateSkill(
        name="Gestión de proyectos",
        normalized_name="gestión de proyectos",
        category=SkillCategory.BUSINESS,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.9,
        years_experience=None,
        references=[reference],
    )
    responsibility = EvidenceItem(
        statement="Coordinó proyectos de transformación digital.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.88,
        references=[reference],
    )
    achievement = achievement or Achievement(
        description="Lideró la implementación de una nueva plataforma interna.",
        measurable_result=None,
        evidence_status=EvidenceStatus.SUPPORTED,
        references=[_reference("Lideró la implementación de una nueva plataforma interna")],
    )
    return CandidateProfessionalProfile(
        professional_identity="Project Manager",
        targetable_roles=["Project Manager"],
        summary="Project Manager con experiencia respaldada en transformación digital y gestión de riesgos.",
        total_years_experience=None,
        seniority=SeniorityLevel.MANAGER,
        industries=["Tecnología"],
        employment_history=[
            EmploymentEntry(
                employer="Empresa Demostración",
                role_title="Senior Project Manager",
                start_date="2018",
                end_date="2025",
                responsibilities=[responsibility],
                achievements=[achievement],
                technologies=[skill],
                industries=["Tecnología"],
            )
        ],
        skills=[skill],
        leadership_capabilities=[responsibility],
        education=[
            EvidenceItem(
                statement="Maestría en Administración de Tecnologías.",
                status=EvidenceStatus.SUPPORTED,
                category=SkillCategory.BUSINESS,
                confidence=0.95,
                references=[_reference("Maestría en Administración de Tecnologías.")],
            )
        ],
        languages=[
            EvidenceItem(
                statement="Español nativo.",
                status=EvidenceStatus.SUPPORTED,
                category=SkillCategory.LANGUAGE,
                confidence=0.95,
                references=[_reference("Español nativo.")],
            )
        ],
        achievements=[achievement],
        ambiguities=["No se especifica tamaño de equipo."],
    )


def _reference(excerpt: str) -> EvidenceReference:
    return EvidenceReference(source_section="CV - Experiencia", source_excerpt=excerpt)
