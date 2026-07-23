from __future__ import annotations

from services.application_communication_audit_service import audit_application_communication_kit
from tests.application_communication_helpers import (
    build_application_communication_inputs,
    build_application_communication_kit,
)


def test_audit_accepts_evidence_backed_communication_kit():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(1)

    result = audit_application_communication_kit(
        kit,
        profile,
        market.job_analyses[0],
        compatibility.job_compatibilities[0],
        targeted_cvs[1],
    )

    assert result.passed
    assert result.word_counts["cover_letter"] == kit.cover_letter.word_count
    assert result.character_counts["recruiter_message"] == kit.recruiter_message.character_count


def test_audit_rejects_wrong_job_and_missing_keyword_claimed_as_skill():
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    kit = build_application_communication_kit(2)
    bad_cover = kit.cover_letter.model_copy(
        update={
            "full_text": kit.cover_letter.full_text + "\n\nTambién cuento con dominio de Kubernetes.",
            "word_count": kit.cover_letter.word_count + 5,
            "keywords_used": [*kit.cover_letter.keywords_used, "Kubernetes"],
        }
    )
    bad = kit.model_copy(update={"target_job_index": 1, "cover_letter": bad_cover})

    result = audit_application_communication_kit(
        bad,
        profile,
        market.job_analyses[1],
        compatibility.job_compatibilities[1],
        targeted_cvs[2],
    )

    assert not result.passed
    messages = " ".join(finding.message for finding in result.findings)
    assert "índice" in messages
    assert "sin respaldo" in messages
