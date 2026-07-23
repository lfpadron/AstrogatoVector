from __future__ import annotations

from services.privacy_filter import REDACTION_TOKEN, redact_sensitive_patterns


def test_redacts_rfc_curp_bank_account_card_and_password_without_original_values():
    text = (
        "María Ejemplo RFC: EIMJ800101ABC CURP: EIMJ800101MDFXXX09 "
        "cuenta 123456789012345678 password: secreto123 tarjeta 4111 1111 1111 1111"
    )

    result = redact_sensitive_patterns(text)

    assert result.redaction_count >= 5
    assert REDACTION_TOKEN in result.filtered_text
    assert "EIMJ800101ABC" not in result.filtered_text
    assert "EIMJ800101MDFXXX09" not in result.filtered_text
    assert "secreto123" not in result.filtered_text
    assert {"RFC", "CURP", "bank_account", "password", "payment_card"}.issubset(
        set(result.detected_categories)
    )


def test_text_without_sensitive_patterns_is_unchanged():
    text = "María Ejemplo trabajó en Empresa Demostración con Python y gestión de riesgos."

    result = redact_sensitive_patterns(text)

    assert result.filtered_text == text
    assert result.redaction_count == 0
    assert result.detected_categories == []
    assert "María Ejemplo" in result.filtered_text
    assert "Empresa Demostración" in result.filtered_text
    assert "Python" in result.filtered_text


def test_multiple_redactions_count_without_storing_originals():
    text = "RFC ABCD991231ZZ1 y RFC XAXX010101000."

    result = redact_sensitive_patterns(text)

    assert result.redaction_count == 2
    assert result.detected_categories == ["RFC"]
    assert "ABCD991231ZZ1" not in str(result.model_dump())
    assert "XAXX010101000" not in str(result.model_dump())
