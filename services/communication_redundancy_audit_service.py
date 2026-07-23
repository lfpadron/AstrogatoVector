"""Heuristic redundancy audit for application communication copy."""

from __future__ import annotations

import re
import unicodedata
from itertools import combinations

from schemas.application_communication_models import (
    ApplicationCommunicationAuditFinding,
    ApplicationCommunicationKit,
    CommunicationRedundancyAuditResult,
)
from schemas.targeted_cv_models import TargetedCV

MAX_COVER_LETTER_CV_SENTENCE_OVERLAP = 0.45
MAX_EMAIL_COVER_LETTER_OVERLAP = 0.55
MAX_RECRUITER_COVER_LETTER_OVERLAP = 0.40
MAX_IDENTICAL_PHRASE_WORDS = 14

_WORD_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def audit_communication_redundancy(
    kit: ApplicationCommunicationKit,
    targeted_cv: TargetedCV,
) -> CommunicationRedundancyAuditResult:
    """Compare communication pieces against each other and the targeted CV."""
    findings: list[ApplicationCommunicationAuditFinding] = []
    metrics: dict[str, float] = {}
    pieces = {
        "cover_letter": kit.cover_letter.full_text,
        "recruiter_message": kit.recruiter_message.message,
        "application_email": kit.application_email.full_text,
        "targeted_cv": _targeted_cv_text(targeted_cv),
    }
    _audit_pair(
        "cover_letter",
        "targeted_cv",
        pieces,
        MAX_COVER_LETTER_CV_SENTENCE_OVERLAP,
        metrics,
        findings,
    )
    _audit_pair(
        "application_email",
        "cover_letter",
        pieces,
        MAX_EMAIL_COVER_LETTER_OVERLAP,
        metrics,
        findings,
    )
    _audit_pair(
        "recruiter_message",
        "cover_letter",
        pieces,
        MAX_RECRUITER_COVER_LETTER_OVERLAP,
        metrics,
        findings,
    )
    _audit_pair(
        "application_email",
        "recruiter_message",
        pieces,
        MAX_EMAIL_COVER_LETTER_OVERLAP,
        metrics,
        findings,
    )
    _audit_cv_bullet_copy(kit, targeted_cv, findings)
    return CommunicationRedundancyAuditResult(
        passed=not any(finding.severity == "error" for finding in findings),
        findings=findings,
        metrics=metrics,
    )


def _audit_pair(
    left_name: str,
    right_name: str,
    pieces: dict[str, str],
    max_overlap: float,
    metrics: dict[str, float],
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    left = pieces[left_name]
    right = pieces[right_name]
    sentence_overlap = _sentence_overlap(left, right)
    ngram_overlap = _ngram_jaccard(left, right, 3)
    longest_phrase = _longest_common_phrase_words(left, right)
    metric_prefix = f"{left_name}_vs_{right_name}"
    metrics[f"{metric_prefix}_sentence_overlap"] = round(sentence_overlap, 3)
    metrics[f"{metric_prefix}_ngram_jaccard"] = round(ngram_overlap, 3)
    metrics[f"{metric_prefix}_longest_identical_phrase_words"] = float(longest_phrase)
    if sentence_overlap > max_overlap:
        _error(
            findings,
            metric_prefix,
            "Hay demasiadas frases idénticas o casi idénticas entre piezas; reescribe con función distinta.",
        )
    if ngram_overlap > max_overlap:
        _warning(
            findings,
            metric_prefix,
            "El vocabulario y orden de frases se parece demasiado; revisa redundancia.",
        )
    if longest_phrase > MAX_IDENTICAL_PHRASE_WORDS:
        _error(
            findings,
            metric_prefix,
            f"Hay una frase idéntica de más de {MAX_IDENTICAL_PHRASE_WORDS} palabras.",
        )


def _audit_cv_bullet_copy(
    kit: ApplicationCommunicationKit,
    targeted_cv: TargetedCV,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    communication = _norm(
        "\n".join(
            [
                kit.cover_letter.full_text,
                kit.recruiter_message.message,
                kit.application_email.full_text,
            ]
        )
    )
    copied = 0
    total = 0
    for entry in targeted_cv.experience:
        for bullet in entry.bullets:
            bullet_norm = _norm(bullet.text)
            if len(_tokens(bullet_norm)) < 8:
                continue
            total += 1
            if bullet_norm and bullet_norm in communication:
                copied += 1
                _error(findings, "targeted_cv.bullets", "Una pieza copia completo un bullet del CV específico.")
    if total and copied / total > 0.35:
        _error(findings, "targeted_cv.bullets", "Varias piezas copian bullets completos del CV específico.")


def _targeted_cv_text(targeted_cv: TargetedCV) -> str:
    values = [targeted_cv.summary.text]
    values.extend(skill.name for skill in targeted_cv.skills)
    for entry in targeted_cv.experience:
        values.append(entry.display_role_title)
        values.append(entry.employer)
        values.extend(bullet.text for bullet in entry.bullets)
        values.extend(entry.technologies)
    return "\n".join(values)


def _sentence_overlap(left: str, right: str) -> float:
    left_sentences = {sentence for sentence in _sentences(left) if len(_tokens(sentence)) >= 6}
    right_sentences = {sentence for sentence in _sentences(right) if len(_tokens(sentence)) >= 6}
    if not left_sentences or not right_sentences:
        return 0.0
    return len(left_sentences & right_sentences) / max(1, min(len(left_sentences), len(right_sentences)))


def _ngram_jaccard(left: str, right: str, size: int) -> float:
    left_ngrams = _ngrams(_tokens(left), size)
    right_ngrams = _ngrams(_tokens(right), size)
    if not left_ngrams or not right_ngrams:
        return 0.0
    return len(left_ngrams & right_ngrams) / len(left_ngrams | right_ngrams)


def _longest_common_phrase_words(left: str, right: str) -> int:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0
    longest = 0
    right_positions: dict[str, list[int]] = {}
    for index, token in enumerate(right_tokens):
        right_positions.setdefault(token, []).append(index)
    for left_index, token in enumerate(left_tokens):
        for right_index in right_positions.get(token, []):
            current = 0
            while (
                left_index + current < len(left_tokens)
                and right_index + current < len(right_tokens)
                and left_tokens[left_index + current] == right_tokens[right_index + current]
            ):
                current += 1
            longest = max(longest, current)
    return longest


def _sentences(text: str) -> list[str]:
    return [_norm(sentence) for sentence in _SENTENCE_SPLIT.split(text or "") if _norm(sentence)]


def _ngrams(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return set()
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _tokens(text: str) -> list[str]:
    return [_norm(match.group(0)) for match in _WORD_PATTERN.finditer(text or "")]


def _norm(value: object) -> str:
    text = str(value or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text)


def _error(findings: list[ApplicationCommunicationAuditFinding], path: str, message: str) -> None:
    findings.append(ApplicationCommunicationAuditFinding(severity="error", path=path, message=message))


def _warning(findings: list[ApplicationCommunicationAuditFinding], path: str, message: str) -> None:
    findings.append(ApplicationCommunicationAuditFinding(severity="warning", path=path, message=message))
