from __future__ import annotations

from services.prompt_loader import load_prompt


def test_editorial_plan_prompt_declares_boundaries_and_no_autopublish():
    prompt = load_prompt("generate_editorial_plan.txt").casefold()
    guardrails = load_prompt("system_guardrails.txt").casefold()

    assert "candidateprofessionalprofile" in prompt
    assert "compatibilityreport" in prompt
    assert "auditreport" in prompt
    assert "exactamente 12 publicaciones" in prompt
    assert "no uses clickbait" in prompt
    assert "plan editorial profesional" in guardrails
    assert "publicacion automatica" in guardrails
