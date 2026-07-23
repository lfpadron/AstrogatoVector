from __future__ import annotations

from services.communication_redundancy_audit_service import audit_communication_redundancy
from tests.application_communication_helpers import build_application_communication_kit
from tests.targeted_cv_helpers import build_targeted_cv


def test_redundancy_audit_accepts_distinct_pieces_with_shared_keywords():
    kit = build_application_communication_kit(1)
    cv = build_targeted_cv(1)

    result = audit_communication_redundancy(kit, cv)

    assert result.passed
    assert result.findings == []
    assert result.metrics["cover_letter_vs_targeted_cv_ngram_jaccard"] < 0.45


def test_redundancy_audit_rejects_cv_bullet_copy():
    kit = build_application_communication_kit(1)
    cv = build_targeted_cv(1)
    copied_text = kit.cover_letter.full_text + "\n\n" + cv.experience[0].bullets[0].text
    bad_cover = kit.cover_letter.model_copy(update={"full_text": copied_text, "word_count": kit.cover_letter.word_count + 14})
    bad = kit.model_copy(update={"cover_letter": bad_cover})

    result = audit_communication_redundancy(bad, cv)

    assert not result.passed
    assert any("bullet" in finding.message for finding in result.findings)
