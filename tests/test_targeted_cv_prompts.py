from __future__ import annotations

from services.prompt_loader import load_prompt


def test_targeted_cv_prompt_defines_evidence_boundaries():
    prompt = load_prompt("generate_targeted_cv.txt")
    guardrails = load_prompt("system_guardrails.txt")

    assert "NO USAR COMO EVIDENCIA" in prompt
    assert "LinkedInProfileOutput" in prompt
    assert "CV crudo" in prompt
    assert "TargetedCV" in prompt
    assert "GENERACION DE CV POR VACANTE" in guardrails
    assert "No uses LinkedInProfileOutput" in guardrails
