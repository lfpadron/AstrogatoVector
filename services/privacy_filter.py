"""Limited preventive sensitive-data redaction before AI calls."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from schemas.extraction_models import PrivacyFilterResult

REDACTION_TOKEN = "[REDACTED_SENSITIVE_DATA]"


@dataclass(frozen=True)
class _PatternRule:
    category: str
    pattern: re.Pattern[str]


_RULES: tuple[_PatternRule, ...] = (
    _PatternRule(
        "CURP",
        re.compile(r"\b[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE),
    ),
    _PatternRule(
        "RFC",
        re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE),
    ),
    _PatternRule(
        "password",
        re.compile(
            r"\b(?:password|contrasena|contrase(?:ñ|n)a|clave)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
    _PatternRule(
        "official_id",
        re.compile(
            r"\b(?:INE|IFE|pasaporte|passport|cedula|c[eé]dula|id oficial)\s*[:#-]?\s*[A-Z0-9-]{6,}\b",
            re.IGNORECASE,
        ),
    ),
    _PatternRule(
        "bank_account",
        re.compile(r"\b(?:cuenta|clabe|account)\s*[:#-]?\s*\d(?:[\s-]?\d){9,23}\b", re.IGNORECASE),
    ),
    _PatternRule(
        "payment_card",
        re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    ),
)


def redact_sensitive_patterns(text: str) -> PrivacyFilterResult:
    """Redact obvious sensitive identifiers without storing original values."""
    filtered_text = text
    redaction_count = 0
    categories: list[str] = []

    for rule in _RULES:
        filtered_text, count = _redact_rule(filtered_text, rule.pattern)
        if count:
            redaction_count += count
            categories.append(rule.category)

    return PrivacyFilterResult(
        filtered_text=filtered_text,
        redaction_count=redaction_count,
        detected_categories=_unique_preserving_order(categories),
    )


def _redact_rule(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        candidate = match.group(0)
        if pattern.pattern == _RULES[-1].pattern.pattern and not _looks_like_payment_card(candidate):
            return candidate
        count += 1
        return REDACTION_TOKEN

    return pattern.sub(replace, text), count


def _looks_like_payment_card(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 13 or len(digits) > 19:
        return False
    return _luhn_checksum_valid(digits)


def _luhn_checksum_valid(digits: str) -> bool:
    checksum = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        number = int(character)
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        checksum += number
    return checksum % 10 == 0


def _unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
