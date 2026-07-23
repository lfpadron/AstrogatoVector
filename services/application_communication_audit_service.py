"""Local audit for per-vacancy application communication kits."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable

from schemas.application_communication_models import (
    ApplicationCommunicationAuditFinding,
    ApplicationCommunicationAuditResult,
    ApplicationCommunicationKit,
    GreetingStrategy,
)
from schemas.compatibility_models import JobCompatibility
from schemas.enums import EvidenceStatus, RequirementCoverage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import TargetedCV

_WORD_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+(?:[-'][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+)?")
_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s?%?|\b\d{4}\b")
_PLACEHOLDERS = ("[", "]", "{", "}", "xxx", "tbd", "por completar", "pendiente", "lorem ipsum")
_SENSITIVE_PATTERNS = (
    r"\bRFC\b",
    r"\bCURP\b",
    r"\bdomicilio particular\b",
    r"\bfecha de nacimiento\b",
    r"\bestado civil\b",
    r"\bcuenta bancaria\b",
    r"\bcontrase(?:n|ñ)a\b",
    r"\bpasaporte\b",
)
_INTERNAL_TERMS = (
    "request_id",
    "input_tokens",
    "output_tokens",
    "raw_response",
    "compatibility_score",
    "prompt",
    "api key",
)
_SPANISH_CLICHES = (
    "candidato ideal",
    "encajo perfectamente",
    "oportunidad de mis sueños",
    "profesional apasionado",
    "líder nato",
    "lider nato",
    "amplia y exitosa trayectoria sin evidencia",
    "dar el 110%",
    "resultados garantizados",
    "sin duda soy la mejor opción",
    "sin duda soy la mejor opcion",
)
_ENGLISH_CLICHES = (
    "perfect fit",
    "ideal candidate",
    "dream opportunity",
    "passionate professional",
    "results-driven",
    "uniquely qualified",
    "hit the ground running",
    "proven track record without evidence",
    "think outside the box",
    "go-getter",
)
_EXAGGERATED_CLICHES = (
    "resultados garantizados",
    "guaranteed results",
    "sin duda soy la mejor opción",
    "sin duda soy la mejor opcion",
    "best possible choice",
)
_SPAM_SUBJECT_TERMS = ("urgente", "urgent", "!!!", "🔥", "⭐", "🚀")
_CAUTION_TERMS = (
    "revisar",
    "preparar",
    "fortalecer",
    "brecha",
    "aprendizaje",
    "interés en desarrollar",
    "interes en desarrollar",
    "to review",
    "prepare",
    "strengthen",
    "gap",
    "learning",
)


def audit_application_communication_kit(
    kit: ApplicationCommunicationKit,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
) -> ApplicationCommunicationAuditResult:
    """Validate that a communication kit stays inside approved evidence boundaries."""
    findings: list[ApplicationCommunicationAuditFinding] = []
    word_counts = {
        "cover_letter": _word_count(kit.cover_letter.full_text),
        "application_email": _word_count(kit.application_email.full_text),
    }
    character_counts = {
        "recruiter_message": len(kit.recruiter_message.message.strip()),
    }
    _audit_identity(kit, job_analysis, job_compatibility, targeted_cv, findings)
    _audit_presence(kit, findings)
    _audit_lengths(kit, word_counts, character_counts, findings)
    _audit_greetings(kit, findings)
    _audit_subjects(kit, job_analysis, findings)
    _audit_text_safety(kit, findings)
    _audit_claims(kit, candidate_profile, job_analysis, job_compatibility, targeted_cv, findings)
    _audit_keywords_and_gaps(kit, candidate_profile, job_analysis, job_compatibility, targeted_cv, findings)
    return ApplicationCommunicationAuditResult(
        passed=not _has_errors(findings),
        findings=findings,
        word_counts=word_counts,
        character_counts=character_counts,
    )


def communication_text(kit: ApplicationCommunicationKit) -> str:
    """Return all public communication text for local checks."""
    values = [
        kit.cover_letter.greeting,
        kit.cover_letter.full_text,
        kit.cover_letter.sign_off,
        kit.recruiter_message.message,
        kit.recruiter_message.call_to_action,
        kit.application_email.greeting,
        kit.application_email.full_text,
        kit.application_email.sign_off,
        kit.application_email.call_to_action,
        "\n".join(kit.application_email.subject_options),
        "\n".join(kit.calls_to_action),
        "\n".join(kit.personalization_notes),
        "\n".join(kit.risks_or_claims_requiring_review),
    ]
    return "\n".join(value for value in values if value)


def count_words(text: str) -> int:
    """Count natural-language words using the same logic as the audit."""
    return _word_count(text)


def _audit_identity(
    kit: ApplicationCommunicationKit,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    if kit.target_job_index != job_analysis.job_index or kit.target_job_index != job_compatibility.job_index:
        _error(findings, "target_job_index", "El índice de vacante no coincide con el análisis y compatibilidad.")
    if kit.target_job_index != targeted_cv.target_job_index:
        _error(findings, "target_job_index", "El kit no corresponde al CV específico de la misma vacante.")
    if _norm(kit.target_job_title) != _norm(job_analysis.title):
        _error(findings, "target_job_title", "El título objetivo no coincide con JobAnalysis.")
    if _norm(kit.target_job_title) != _norm(targeted_cv.target_job_title):
        _error(findings, "target_job_title", "El título objetivo no coincide con el CV específico.")
    if _norm(kit.target_company or "") != _norm(job_analysis.company or ""):
        _error(findings, "target_company", "La empresa objetivo no coincide con JobAnalysis.")
    if _norm(job_compatibility.job_title) != _norm(job_analysis.title):
        _error(findings, "job_compatibility.job_title", "La compatibilidad no corresponde a la vacante auditada.")
    if kit.compatibility_score is not None and abs(kit.compatibility_score - job_compatibility.compatibility_score) > 0.11:
        _error(findings, "compatibility_score", "El score técnico declarado no coincide con JobCompatibility.")
    if kit.compatibility_band and _norm(kit.compatibility_band) != _norm(job_compatibility.compatibility_band):
        _error(findings, "compatibility_band", "La banda técnica declarada no coincide con JobCompatibility.")
    if kit.targeted_cv_version and kit.targeted_cv_version != targeted_cv.cv_version:
        _warning(findings, "targeted_cv_version", "La versión del CV específico declarada no coincide.")


def _audit_presence(kit: ApplicationCommunicationKit, findings: list[ApplicationCommunicationAuditFinding]) -> None:
    if not kit.cover_letter.full_text.strip():
        _error(findings, "cover_letter.full_text", "La carta de presentación está vacía.")
    if not kit.recruiter_message.message.strip():
        _error(findings, "recruiter_message.message", "El mensaje para recruiter está vacío.")
    if not kit.application_email.full_text.strip():
        _error(findings, "application_email.full_text", "El correo de postulación está vacío.")
    if not kit.application_email.subject_options:
        _error(findings, "application_email.subject_options", "Debe existir al menos un asunto sugerido.")
    if not kit.calls_to_action:
        _warning(findings, "calls_to_action", "Agrega llamadas a la acción breves y profesionales.")


def _audit_lengths(
    kit: ApplicationCommunicationKit,
    word_counts: dict[str, int],
    character_counts: dict[str, int],
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    cover_words = word_counts["cover_letter"]
    email_words = word_counts["application_email"]
    recruiter_chars = character_counts["recruiter_message"]
    if kit.cover_letter.word_count != cover_words:
        _error(findings, "cover_letter.word_count", "El conteo declarado no coincide con el conteo local.")
    if kit.application_email.word_count != email_words:
        _error(findings, "application_email.word_count", "El conteo declarado no coincide con el conteo local.")
    if kit.recruiter_message.character_count != recruiter_chars:
        _error(findings, "recruiter_message.character_count", "El conteo declarado no coincide con el conteo local.")
    _audit_range(cover_words, 250, 500, 230, 530, "cover_letter.full_text", "carta de presentación", findings)
    _audit_range(email_words, 140, 320, 125, 345, "application_email.full_text", "correo de postulación", findings)
    _audit_range(
        recruiter_chars,
        280,
        650,
        250,
        700,
        "recruiter_message.message",
        "mensaje para recruiter",
        findings,
    )


def _audit_range(
    value: int,
    minimum: int,
    maximum: int,
    tolerated_minimum: int,
    tolerated_maximum: int,
    path: str,
    label: str,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    if value < tolerated_minimum or value > tolerated_maximum:
        _error(findings, path, f"El {label} debe mantenerse entre {minimum} y {maximum}.")
    elif value < minimum or value > maximum:
        _warning(findings, path, f"El {label} está cerca del límite permitido; revisa extensión.")


def _audit_greetings(kit: ApplicationCommunicationKit, findings: list[ApplicationCommunicationAuditFinding]) -> None:
    greeting_pairs = (
        ("cover_letter", kit.cover_letter.greeting_strategy, kit.cover_letter.greeting),
        ("application_email", kit.application_email.greeting_strategy, kit.application_email.greeting),
    )
    for path, strategy, greeting in greeting_pairs:
        lowered = _norm(greeting)
        if strategy == GreetingStrategy.NAMED_PERSON.value:
            _error(findings, f"{path}.greeting_strategy", "No se puede usar nombre de recruiter si no fue suministrado.")
        if any(marker in lowered for marker in ("[nombre", "[name", "estimado/a [", "dear [")):
            _error(findings, f"{path}.greeting", "El saludo contiene un placeholder de destinatario.")
        if any(marker in greeting for marker in ("[", "]", "{", "}")):
            _error(findings, f"{path}.greeting", "El saludo no debe contener placeholders.")
        if greeting and greeting[-1] not in {",", ":"}:
            _warning(findings, f"{path}.greeting", "Revisa la puntuación final del saludo.")


def _audit_subjects(
    kit: ApplicationCommunicationKit,
    job_analysis: JobAnalysis,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    subjects = kit.application_email.subject_options
    if len(subjects) > 3:
        _error(findings, "application_email.subject_options", "Usa entre uno y tres asuntos sugeridos.")
    for index, subject in enumerate(subjects):
        path = f"application_email.subject_options[{index}]"
        length = len(subject.strip())
        if length < 20 or length > 120:
            _error(findings, path, "El asunto debe tener entre 20 y 120 caracteres.")
        lowered = _norm(subject)
        if any(term in lowered for term in _SPAM_SUBJECT_TERMS):
            _error(findings, path, "El asunto parece urgente, promocional o spam.")
        if "disponibilidad inmediata" in lowered or "immediate availability" in lowered:
            _error(findings, path, "No prometas disponibilidad inmediata si no fue suministrada.")
        if "score" in lowered or "compatibilidad" in lowered:
            _error(findings, path, "El asunto no debe mencionar scores ni compatibilidad técnica.")
        if _norm(job_analysis.title) not in lowered and "postul" not in lowered and "application" not in lowered:
            _warning(findings, path, "Incluye el rol objetivo o la intención de postulación.")


def _audit_text_safety(
    kit: ApplicationCommunicationKit,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    text = communication_text(kit)
    lowered = _norm(text)
    for placeholder in _PLACEHOLDERS:
        if placeholder in lowered:
            _error(findings, "communication_text", f"El texto contiene placeholder o contenido incompleto: {placeholder}.")
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            _error(findings, "communication_text", "El texto contiene información sensible no permitida.")
    for term in _INTERNAL_TERMS:
        if term in lowered:
            _error(findings, "communication_text", f"El texto contiene marcador interno no permitido: {term}.")
    for phrase in _SPANISH_CLICHES + _ENGLISH_CLICHES:
        if _norm(phrase) in lowered:
            if _norm(phrase) in {_norm(value) for value in _EXAGGERATED_CLICHES}:
                _error(findings, "communication_text", f"El texto contiene exageración no permitida: {phrase}.")
            else:
                _warning(findings, "communication_text", f"El texto contiene cliché que conviene editar: {phrase}.")
    if re.search(r"\b(score|compatibilidad|ats)\b", lowered) and re.search(r"\b\d{1,3}(?:[.,]\d)?\b", lowered):
        _error(findings, "communication_text", "No incluyas scores técnicos en piezas de postulación.")


def _audit_claims(
    kit: ApplicationCommunicationKit,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    source_text = _source_text(candidate_profile, job_analysis, job_compatibility, targeted_cv)
    supported_numbers = {_number_norm(match.group(0)) for match in _NUMBER_PATTERN.finditer(source_text)}
    text = communication_text(kit)
    for match in _NUMBER_PATTERN.finditer(text):
        value = _number_norm(match.group(0))
        if value and value not in supported_numbers:
            _error(findings, "communication_text", f"La cifra '{match.group(0)}' no aparece respaldada.")

    for path, claims in (
        ("cover_letter.claims", kit.cover_letter.claims),
        ("recruiter_message.claims", kit.recruiter_message.claims),
        ("application_email.claims", kit.application_email.claims),
    ):
        for index, claim in enumerate(claims):
            claim_path = f"{path}[{index}]"
            status = str(claim.evidence_status)
            if status in {EvidenceStatus.MISSING.value, EvidenceStatus.CONFLICT.value}:
                _error(findings, claim_path, "No presentes información MISSING o CONFLICT como capacidad.")
            if status == EvidenceStatus.INFERRED.value and not claim.needs_review:
                _warning(findings, claim_path, "Las inferencias deben marcarse con cautela para revisión humana.")
            if status == EvidenceStatus.SUPPORTED.value and not _phrase_has_any_support(claim.text, source_text):
                _warning(findings, claim_path, "El claim no aparece literalmente en las fuentes reducidas; revisa redacción.")


def _audit_keywords_and_gaps(
    kit: ApplicationCommunicationKit,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
    findings: list[ApplicationCommunicationAuditFinding],
) -> None:
    supported_terms = {_norm(term) for term in _supported_terms(candidate_profile, job_compatibility, targeted_cv)}
    job_terms = {_norm(term) for term in _job_terms(job_analysis)}
    missing_terms = {_norm(term) for term in [*job_compatibility.critical_gaps, *job_compatibility.other_gaps]}
    communication_terms = [
        *kit.cover_letter.keywords_used,
        *kit.recruiter_message.keywords_used,
        *kit.application_email.keywords_used,
    ]
    for keyword in communication_terms:
        normalized = _norm(keyword)
        if not normalized:
            continue
        if normalized not in supported_terms and normalized in job_terms:
            _error(findings, "keywords_used", "Una keyword de la vacante se está usando sin respaldo profesional.")
        elif normalized not in supported_terms:
            _warning(findings, "keywords_used", "Una keyword declarada no aparece respaldada en el perfil o CV específico.")

    text = _norm(communication_text(kit))
    for gap in missing_terms:
        if gap and gap in text and not any(term in text for term in _CAUTION_TERMS):
            _error(findings, "communication_text", "Una brecha aparece redactada como capacidad sin cautela.")


def _supported_terms(
    candidate_profile: CandidateProfessionalProfile,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
) -> Iterable[str]:
    for skill in candidate_profile.skills:
        if _is_supported(skill.evidence_status):
            yield skill.name
            yield skill.normalized_name
    for item in candidate_profile.leadership_capabilities:
        if _is_supported(item.status):
            yield item.statement
    for match in job_compatibility.requirement_matches:
        if _is_supported(match.evidence_status) and _coverage_is_usable(match.coverage):
            yield match.requirement_name
            yield match.normalized_requirement
            yield from match.matched_candidate_items
    for skill in targeted_cv.skills:
        if _is_supported(skill.evidence_status):
            yield skill.name
    yield from targeted_cv.ats_keywords_used
    for entry in targeted_cv.experience:
        yield entry.display_role_title
        yield from entry.technologies
        yield from entry.industries
        for bullet in entry.bullets:
            yield bullet.text


def _job_terms(job_analysis: JobAnalysis) -> Iterable[str]:
    yield job_analysis.title
    yield from job_analysis.exact_keywords
    yield from job_analysis.technical_skills
    yield from job_analysis.soft_skills
    yield from job_analysis.leadership_skills
    yield from job_analysis.tools_and_technologies
    yield from job_analysis.industries
    yield from job_analysis.certifications
    for requirement in job_analysis.requirements:
        yield requirement.name
        yield requirement.normalized_name
        yield from requirement.exact_keywords


def _source_text(
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
    targeted_cv: TargetedCV,
) -> str:
    payload = {
        "candidate": candidate_profile.model_dump(mode="json"),
        "job": job_analysis.model_dump(mode="json"),
        "compatibility": job_compatibility.model_dump(mode="json"),
        "targeted_cv": targeted_cv.model_dump(mode="json"),
    }
    return json.dumps(payload, ensure_ascii=False)


def _phrase_has_any_support(phrase: str, source_text: str) -> bool:
    phrase_tokens = [token for token in _tokens(phrase) if len(token) >= 4]
    if not phrase_tokens:
        return False
    source_norm = _norm(source_text)
    hits = sum(1 for token in set(phrase_tokens) if token in source_norm)
    return hits / max(1, len(set(phrase_tokens))) >= 0.35


def _coverage_is_usable(value: object) -> bool:
    return str(getattr(value, "value", value)) in {
        RequirementCoverage.FULL.value,
        RequirementCoverage.PARTIAL.value,
        RequirementCoverage.INDIRECT.value,
    }


def _is_supported(value: object) -> bool:
    return str(getattr(value, "value", value)) == EvidenceStatus.SUPPORTED.value


def _has_errors(findings: list[ApplicationCommunicationAuditFinding]) -> bool:
    return any(finding.severity == "error" for finding in findings)


def _error(findings: list[ApplicationCommunicationAuditFinding], path: str, message: str) -> None:
    findings.append(ApplicationCommunicationAuditFinding(severity="error", path=path, message=message))


def _warning(findings: list[ApplicationCommunicationAuditFinding], path: str, message: str) -> None:
    findings.append(ApplicationCommunicationAuditFinding(severity="warning", path=path, message=message))


def _word_count(text: str) -> int:
    return len(_WORD_PATTERN.findall(text or ""))


def _tokens(text: str) -> list[str]:
    return [_norm(match.group(0)) for match in _WORD_PATTERN.finditer(text or "")]


def _norm(value: object) -> str:
    text = str(value or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text)


def _number_norm(value: str) -> str:
    return value.replace(" ", "").replace(",", ".")
