from __future__ import annotations

from schemas.compatibility_models import (
    COMPATIBILITY_BAND_LABELS_EN,
    COMPATIBILITY_BAND_LABELS_ES,
    COMPATIBILITY_DIMENSION_WEIGHTS,
    COMPATIBILITY_DISCLAIMER_EN,
    COMPATIBILITY_DISCLAIMER_ES,
    COMPATIBILITY_METHODOLOGY_VERSION,
    compatibility_band_for_score,
)
from services.compatibility_scoring_service import (
    CRITICAL_REQUIRED_MISSING_PENALTY,
    EVIDENCE_STATUS_FACTORS,
    MAX_CRITICAL_MISSING_PENALTY,
    REQUIREMENT_PRIORITY_WEIGHTS,
)


def test_dimension_weights_sum_to_one():
    assert COMPATIBILITY_METHODOLOGY_VERSION == "1.0"
    assert sum(COMPATIBILITY_DIMENSION_WEIGHTS.values()) == 1.0
    assert COMPATIBILITY_DIMENSION_WEIGHTS["experience_responsibilities"] == 0.30
    assert COMPATIBILITY_DIMENSION_WEIGHTS["education_certifications_languages"] == 0.08


def test_bands_and_labels_are_not_hiring_probability_labels():
    assert compatibility_band_for_score(85.0) == "very_high"
    assert compatibility_band_for_score(70.0) == "high"
    assert compatibility_band_for_score(55.0) == "moderate"
    assert compatibility_band_for_score(40.0) == "low"
    assert compatibility_band_for_score(0.0) == "very_low"
    labels = " ".join([*COMPATIBILITY_BAND_LABELS_ES.values(), *COMPATIBILITY_BAND_LABELS_EN.values()])
    assert "contratado" not in labels.casefold()
    assert "probable" not in labels.casefold()


def test_disclaimer_mentions_not_hiring_probability():
    assert "probabilidad de contratación" in COMPATIBILITY_DISCLAIMER_ES
    assert "hiring probability" in COMPATIBILITY_DISCLAIMER_EN


def test_scoring_constants_match_prompt():
    assert EVIDENCE_STATUS_FACTORS["SUPPORTED"] == 1.0
    assert EVIDENCE_STATUS_FACTORS["INFERRED"] == 0.75
    assert REQUIREMENT_PRIORITY_WEIGHTS["critical"] == 1.5
    assert CRITICAL_REQUIRED_MISSING_PENALTY == 5.0
    assert MAX_CRITICAL_MISSING_PENALTY == 20.0
