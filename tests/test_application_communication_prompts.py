from __future__ import annotations

from services.prompt_loader import load_prompt


def test_application_communication_prompt_has_guardrails_and_output_contract():
    prompt = load_prompt("generate_application_communications.txt")

    assert "ApplicationCommunicationKit" in prompt
    assert "NO USAR COMO EVIDENCIA" in prompt
    assert "CV original" in prompt
    assert "LinkedInProfileOutput" in prompt
    assert "No inventes" in prompt
    assert "250 a 500 palabras" in prompt


def test_system_guardrails_include_application_communication_section():
    guardrails = load_prompt("system_guardrails.txt")

    assert "COMUNICACION DE POSTULACION" in guardrails
    assert "No inventes nombres de recruiters" in guardrails
    assert "No conviertas brechas criticas" in guardrails
