from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.enums import EvidenceStatus, SkillCategory
from schemas.evidence_models import CandidateSkill, EvidenceItem, EvidenceReference


def _reference() -> EvidenceReference:
    return EvidenceReference(source_section="CV ficticio", source_excerpt="Coordinación de equipos.")


def test_supported_evidence_with_reference_is_valid():
    item = EvidenceItem(
        statement="Coordina equipos multifuncionales.",
        status=EvidenceStatus.SUPPORTED,
        category=SkillCategory.LEADERSHIP,
        confidence=0.8,
        references=[_reference()],
    )

    assert item.status == "SUPPORTED"


def test_supported_evidence_without_reference_fails():
    with pytest.raises(ValidationError):
        EvidenceItem(
            statement="Coordina equipos multifuncionales.",
            status=EvidenceStatus.SUPPORTED,
            confidence=0.8,
        )


def test_missing_evidence_without_reference_is_valid():
    item = EvidenceItem(
        statement="Certificación no encontrada.",
        status=EvidenceStatus.MISSING,
        confidence=0.2,
    )

    assert item.references == []


def test_conflict_without_notes_fails():
    with pytest.raises(ValidationError):
        EvidenceItem(
            statement="Fechas de empleo inconsistentes.",
            status=EvidenceStatus.CONFLICT,
            confidence=0.6,
            references=[_reference()],
        )


def test_negative_years_experience_fails():
    with pytest.raises(ValidationError):
        CandidateSkill(
            name="Python",
            normalized_name="python",
            category=SkillCategory.TECHNICAL,
            evidence_status=EvidenceStatus.INFERRED,
            confidence=0.5,
            years_experience=-1,
        )
