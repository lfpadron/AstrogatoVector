from __future__ import annotations

from services.prompt_loader import load_prompt


def test_system_guardrails_include_linkedin_profile_generation_rules():
    prompt = load_prompt("system_guardrails.txt").casefold()

    assert "generacion de perfil de linkedin" in prompt
    assert "candidateprofessionalprofile" in prompt
    assert "targetmarketanalysis" in prompt
    assert "nunca conviertas un requisito del mercado" in prompt
    assert "seguridad de generacion" in prompt
    assert "no utilices conocimiento externo" in prompt


def test_generate_profile_prompt_defines_linkedin_profile_output_contract():
    prompt = load_prompt("generate_profile.txt").casefold()

    assert "linkedinprofileoutput" in prompt
    assert "candidate_evidence" not in prompt
    assert "el mercado define el vocabulario" in prompt
    assert "solo incorpora como capacidades" in prompt
    assert "banner" in prompt
    assert "headline" in prompt
    assert "about" in prompt
    assert "experiencia reescrita" in prompt
    assert "skills priorizadas" in prompt
    assert "keywords ats" in prompt
    assert "no generar la imagen" in prompt
    assert "supported_by_candidate=false" in prompt
