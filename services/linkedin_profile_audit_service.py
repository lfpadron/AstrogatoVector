"""Deterministic checks for generated LinkedIn profile output."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from schemas.enums import EvidenceStatus, SeniorityLevel
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
)
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_generation_models import LinkedInProfileAuditFinding, LinkedInProfileAuditResult
from schemas.profile_models import ATSKeyword, LinkedInProfileOutput, PrioritizedSkill
from services.privacy_filter import redact_sensitive_patterns

PROFILE_CLICHES = {
    "results-driven",
    "passionate professional",
    "dynamic leader",
    "rockstar",
    "ninja",
    "guru",
    "world-class",
    "best-in-class",
    "lider nato",
    "guru",
    "experto de clase mundial",
    "profesional apasionado",
    "resultados garantizados",
    "el mejor",
    "altamente exitoso",
}
ALLOWED_BANNER_TEMPLATES = {
    "professional_light",
    "professional_dark",
    "executive_blue",
    "technology_clean",
}
ALLOWED_PLACEMENTS = {
    "headline",
    "about",
    "experience",
    "skills",
    "projects",
    "certifications",
    "publications",
}
CURRENT_PROFILE_SECTIONS = {"headline", "about", "experience"}
HIGH_SENIORITY_TERMS = {"director", "executive", "head", "chief", "vp", "cxo", "ceo", "cto", "cfo"}
LOWER_SENIORITIES = {
    SeniorityLevel.ENTRY.value,
    SeniorityLevel.MID.value,
    SeniorityLevel.SENIOR.value,
    SeniorityLevel.LEAD.value,
    SeniorityLevel.MANAGER.value,
}


def audit_linkedin_profile_output(
    output: LinkedInProfileOutput,
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
) -> LinkedInProfileAuditResult:
    """Audit generated LinkedIn profile text for evidence and structural consistency."""
    context = _build_context(candidate_profile, market_analysis)
    findings: list[LinkedInProfileAuditFinding] = []

    _audit_banner(output, context, findings)
    _audit_headline(output, context, findings)
    _audit_about(output, candidate_profile, context, findings)
    _audit_experience(output, candidate_profile, context, findings)
    _audit_prioritized_skills(output.prioritized_skills, context, findings)
    _audit_ats_keywords(output.ats_keywords, context, findings)
    _audit_global_consistency(output, candidate_profile, context, findings)

    passed = not any(finding.severity == "error" for finding in findings)
    return LinkedInProfileAuditResult(passed=passed, findings=findings)


def _audit_banner(
    output: LinkedInProfileOutput,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    banner = output.banner
    joined = " ".join(
        value
        for value in (
            banner.primary_line,
            banner.specialty_line,
            banner.supporting_line or "",
            banner.visual_concept,
        )
        if value
    )
    _audit_sensitive_text(joined, "banner", findings)
    _audit_numbers(joined, "banner", context, findings)
    _audit_market_only_terms(joined, "banner", context, findings)
    _audit_cliches(joined, "banner", findings)
    if banner.recommended_template not in ALLOWED_BANNER_TEMPLATES:
        _add_error(findings, "banner.recommended_template", "La plantilla de banner no esta permitida.")
    if _has_contact_data(joined):
        _add_error(findings, "banner", "El banner no debe incluir telefono, correo ni URL.")
    if _concept_found("logo", _normalize_for_match(banner.visual_concept)) and _has_company_name(
        banner.visual_concept,
        context,
    ):
        _add_warning(findings, "banner.visual_concept", "Evita pedir logos o nombres de empresas como instruccion visual.")


def _audit_headline(
    output: LinkedInProfileOutput,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    headline = output.headline
    if not headline.text.strip():
        _add_error(findings, "headline.text", "El headline no puede estar vacio.")
    if len(headline.text) > 220:
        _add_error(findings, "headline.text", "El headline supera 220 caracteres.")
    if headline.character_count != len(headline.text):
        _add_error(findings, "headline.character_count", "character_count debe coincidir con len(text).")
    _audit_sensitive_text(headline.text, "headline.text", findings)
    _audit_numbers(headline.text, "headline.text", context, findings)
    _audit_market_only_terms(headline.text, "headline.text", context, findings)
    _audit_cliches(headline.text, "headline.text", findings)
    _audit_seniority_inflation(headline.text, "headline.text", context, findings)
    _audit_included_keywords(
        headline.included_keywords,
        headline.text,
        "headline.included_keywords",
        context,
        findings,
        require_supported=True,
    )
    _audit_keyword_stuffing(headline.text, "headline.text", findings)


def _audit_about(
    output: LinkedInProfileOutput,
    candidate_profile: CandidateProfessionalProfile,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    about = output.about
    if about.character_count != len(about.text):
        _add_error(findings, "about.character_count", "character_count debe coincidir con len(text).")
    if len(about.text) < 200:
        _add_error(findings, "about.text", "El About debe tener al menos 200 caracteres.")
    if len(about.text) > 3000:
        _add_error(findings, "about.text", "El About supera el limite del contrato.")
    normalized = _normalize_for_match(about.text)
    if not any(marker in normalized for marker in ("soy ", "he ", "mi ", "me ", "i ", "my ", "i have")):
        _add_warning(findings, "about.text", "El About no parece estar escrito en primera persona.")
    _audit_sensitive_text(about.text, "about.text", findings)
    _audit_numbers(about.text, "about.text", context, findings)
    _audit_market_only_terms(about.text, "about.text", context, findings)
    _audit_cliches(about.text, "about.text", findings)
    _audit_seniority_inflation(about.text, "about.text", context, findings)
    _audit_included_keywords(about.included_keywords, about.text, "about.included_keywords", context, findings)
    _audit_keyword_stuffing(about.text, "about.text", findings)
    _audit_unknown_named_items(about.text, candidate_profile, context, "about.text", findings)
    if context["inferred_terms"] and about.claims_requiring_review == []:
        _add_warning(findings, "about.claims_requiring_review", "Registra inferencias usadas o elementos que requieran revisión.")


def _audit_experience(
    output: LinkedInProfileOutput,
    candidate_profile: CandidateProfessionalProfile,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    expected = candidate_profile.employment_history
    actual = output.experience
    if len(actual) != len(expected):
        _add_error(findings, "experience", "Debe existir exactamente una experiencia reescrita por empleo fuente.")
    seen_pairs: set[tuple[str, str]] = set()
    for index, rewritten in enumerate(actual):
        path = f"experience[{index}]"
        if rewritten.unsupported_claims:
            _add_error(findings, f"{path}.unsupported_claims", "unsupported_claims debe estar vacio.")
        pair = (_normalize_key(rewritten.employer), _normalize_key(rewritten.source_role_title))
        if pair in seen_pairs:
            _add_error(findings, path, "Se detecto una experiencia duplicada.")
        seen_pairs.add(pair)
        employment = _matching_employment(rewritten.employer, rewritten.source_role_title, expected)
        if employment is None:
            _add_error(findings, path, "La experiencia no corresponde a un empleo fuente.")
            continue
        if not _titles_correspond(employment.role_title, rewritten.source_role_title):
            _add_error(findings, f"{path}.source_role_title", "El cargo fuente no corresponde al empleo.")
        if _inflates_role(employment.role_title, rewritten.suggested_role_title, context):
            _add_error(findings, f"{path}.suggested_role_title", "El cargo sugerido eleva artificialmente el seniority.")
        _audit_sensitive_text(rewritten.rewritten_text, f"{path}.rewritten_text", findings)
        _audit_numbers(rewritten.rewritten_text, f"{path}.rewritten_text", context, findings)
        _audit_market_only_terms(rewritten.rewritten_text, f"{path}.rewritten_text", context, findings)
        _audit_cliches(rewritten.rewritten_text, f"{path}.rewritten_text", findings)
        _audit_included_keywords(
            rewritten.included_keywords,
            rewritten.rewritten_text,
            f"{path}.included_keywords",
            context,
            findings,
            require_supported=True,
        )


def _audit_prioritized_skills(
    skills: list[PrioritizedSkill],
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    if len(skills) > 50:
        _add_error(findings, "prioritized_skills", "No deben priorizarse mas de 50 skills.")
    ranks = [skill.priority_rank for skill in skills]
    if len(ranks) != len(set(ranks)):
        _add_error(findings, "prioritized_skills", "Los rankings de skills deben ser unicos.")
    if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
        _add_error(findings, "prioritized_skills", "Los rankings de skills deben ser consecutivos.")
    seen: set[str] = set()
    first_inferred_rank: int | None = None
    for index, skill in enumerate(skills):
        path = f"prioritized_skills[{index}]"
        key = _normalize_key(skill.name)
        if key in seen:
            _add_error(findings, path, "Skill duplicada por normalizacion.")
        seen.add(key)
        if not skill.rationale.strip():
            _add_error(findings, f"{path}.rationale", "La razon de priorizacion no puede estar vacia.")
        if skill.evidence_status == EvidenceStatus.MISSING:
            _add_error(findings, f"{path}.evidence_status", "Las skills MISSING no deben aparecer como skills priorizadas.")
        if skill.evidence_status == EvidenceStatus.SUPPORTED and key not in context["supported_skill_keys"]:
            _add_error(findings, path, "La skill SUPPORTED no existe en las skills respaldadas del candidato.")
        if skill.evidence_status == EvidenceStatus.INFERRED:
            if key not in context["candidate_concept_keys"]:
                _add_warning(findings, path, "La skill INFERRED no aparece claramente en el perfil del candidato.")
            first_inferred_rank = skill.priority_rank if first_inferred_rank is None else first_inferred_rank
        if first_inferred_rank is not None and skill.evidence_status == EvidenceStatus.SUPPORTED:
            if skill.priority_rank > first_inferred_rank:
                _add_warning(findings, path, "Las skills SUPPORTED deberian preceder skills INFERRED comparables.")
        _audit_placements(skill.recommended_placement, f"{path}.recommended_placement", findings)


def _audit_ats_keywords(
    keywords: list[ATSKeyword],
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    market_keywords: dict[str, object] = context["market_keywords"]
    seen: set[str] = set()
    for index, keyword in enumerate(keywords):
        path = f"ats_keywords[{index}]"
        key = _normalize_key(keyword.normalized_keyword or keyword.keyword)
        if key in seen:
            _add_error(findings, path, "Keyword ATS duplicada.")
        seen.add(key)
        market_keyword = market_keywords.get(key)
        if market_keyword is None:
            _add_error(findings, path, "La keyword ATS no existe en el mercado objetivo.")
        elif keyword.frequency_in_jobs != market_keyword.frequency:
            _add_error(findings, f"{path}.frequency_in_jobs", "La frecuencia no coincide con el mercado.")
        supported = _is_supported_keyword(key, keyword.keyword, context)
        if keyword.supported_by_candidate != supported:
            _add_error(findings, f"{path}.supported_by_candidate", "El respaldo declarado no coincide con la evidencia.")
        if keyword.supported_by_candidate and keyword.evidence_status != EvidenceStatus.SUPPORTED:
            _add_error(findings, f"{path}.evidence_status", "Una keyword respaldada debe marcarse SUPPORTED.")
        if not keyword.supported_by_candidate and keyword.evidence_status not in {
            EvidenceStatus.MISSING,
            EvidenceStatus.INFERRED,
        }:
            _add_error(findings, f"{path}.evidence_status", "Una keyword no respaldada debe marcarse MISSING o INFERRED.")
        placements = {_normalize_key(section) for section in keyword.recommended_sections}
        _audit_placements(keyword.recommended_sections, f"{path}.recommended_sections", findings)
        if not keyword.supported_by_candidate and placements & CURRENT_PROFILE_SECTIONS:
            _add_error(
                findings,
                f"{path}.recommended_sections",
                "Keywords no respaldadas no deben recomendarse para headline, About o experiencia.",
            )


def _audit_global_consistency(
    output: LinkedInProfileOutput,
    candidate_profile: CandidateProfessionalProfile,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    visible_text = " ".join(
        [
            output.banner.primary_line,
            output.banner.specialty_line,
            output.banner.supporting_line or "",
            output.headline.text,
            output.about.text,
        ]
        + [experience.rewritten_text for experience in output.experience]
    )
    if not _concept_found(candidate_profile.professional_identity, _normalize_for_match(visible_text)):
        _add_warning(findings, "profile_output", "La identidad profesional no aparece claramente en el contenido generado.")
    if candidate_profile.conflicts and not output.global_review_notes:
        _add_warning(findings, "global_review_notes", "Existen conflictos del candidato que deben quedar visibles en notas.")
    missing_market = [
        keyword.keyword
        for keyword in output.ats_keywords
        if not keyword.supported_by_candidate and keyword.evidence_status == EvidenceStatus.MISSING
    ]
    if missing_market and not any(_contains_any(note, missing_market) for note in output.global_review_notes):
        _add_warning(findings, "global_review_notes", "Registra keywords relevantes no respaldadas como revisión o brecha.")


def _build_context(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
) -> dict[str, object]:
    source_text = _candidate_source_text(candidate_profile)
    supported_skill_keys = {
        _normalize_key(skill.normalized_name or skill.name)
        for skill in candidate_profile.skills
        if skill.evidence_status == EvidenceStatus.SUPPORTED
    } | {
        _normalize_key(skill.name)
        for employment in candidate_profile.employment_history
        for skill in employment.technologies
        if skill.evidence_status == EvidenceStatus.SUPPORTED
    }
    supported_concepts = set(supported_skill_keys)
    candidate_concepts = set(supported_skill_keys)
    inferred_terms: set[str] = set()
    for value in _candidate_strings(candidate_profile):
        key = _normalize_key(value)
        if key:
            candidate_concepts.add(key)
    for item in _all_evidence_items(candidate_profile):
        if item.status == EvidenceStatus.SUPPORTED:
            supported_concepts.add(_normalize_key(item.statement))
        elif item.status == EvidenceStatus.INFERRED:
            inferred_terms.add(_normalize_key(item.statement))
    for achievement in _all_achievements(candidate_profile):
        if achievement.evidence_status == EvidenceStatus.SUPPORTED:
            supported_concepts.add(_normalize_key(achievement.description))
    market_keywords = {
        _normalize_key(keyword.normalized_keyword or keyword.keyword): keyword
        for keyword in market_analysis.keywords
    }
    market_terms = {
        _normalize_key(value)
        for value in [
            *market_analysis.technical_skills,
            *market_analysis.leadership_skills,
            *market_analysis.business_skills,
            *market_analysis.tools_and_technologies,
            *market_analysis.industries,
            *(keyword.keyword for keyword in market_analysis.keywords),
        ]
        if value
    }
    market_only_terms = {
        term
        for term in market_terms
        if term and not _term_supported(term, supported_concepts, source_text)
    }
    return {
        "source_text": source_text,
        "supported_skill_keys": supported_skill_keys,
        "supported_concepts": supported_concepts,
        "candidate_concept_keys": candidate_concepts,
        "inferred_terms": inferred_terms,
        "market_keywords": market_keywords,
        "market_only_terms": market_only_terms,
        "candidate_seniority": _enum_value(candidate_profile.seniority),
        "employers": {_normalize_key(employer) for employer in _employment_employers(candidate_profile)},
        "companies": {_normalize_key(company) for company in _employment_employers(candidate_profile)},
    }


def _candidate_source_text(candidate_profile: CandidateProfessionalProfile) -> str:
    values = list(_candidate_strings(candidate_profile))
    return _normalize_for_match(" ".join(values))


def _candidate_strings(candidate_profile: CandidateProfessionalProfile):
    yield candidate_profile.professional_identity
    yield candidate_profile.summary
    yield str(candidate_profile.total_years_experience or "")
    yield from candidate_profile.targetable_roles
    yield from candidate_profile.industries
    yield from candidate_profile.ambiguities
    yield from candidate_profile.conflicts
    yield from candidate_profile.missing_information
    for employment in candidate_profile.employment_history:
        yield employment.employer
        yield employment.role_title
        yield employment.start_date or ""
        yield employment.end_date or ""
        yield employment.location or ""
        yield from employment.industries
        for item in employment.responsibilities:
            yield item.statement
            yield item.notes or ""
            for reference in item.references:
                yield reference.source_excerpt
        for achievement in employment.achievements:
            yield achievement.description
            yield achievement.measurable_result or ""
            for reference in achievement.references:
                yield reference.source_excerpt
        for skill in employment.technologies:
            yield skill.name
            yield skill.normalized_name
    for skill in candidate_profile.skills:
        yield skill.name
        yield skill.normalized_name
    for item in _all_evidence_items(candidate_profile):
        yield item.statement
        yield item.notes or ""
        for reference in item.references:
            yield reference.source_excerpt
    for achievement in candidate_profile.achievements:
        yield achievement.description
        yield achievement.measurable_result or ""


def _all_evidence_items(candidate_profile: CandidateProfessionalProfile):
    yield from candidate_profile.leadership_capabilities
    yield from candidate_profile.education
    yield from candidate_profile.certifications
    yield from candidate_profile.languages
    for employment in candidate_profile.employment_history:
        yield from employment.responsibilities


def _all_achievements(candidate_profile: CandidateProfessionalProfile):
    yield from candidate_profile.achievements
    for employment in candidate_profile.employment_history:
        yield from employment.achievements


def _employment_employers(candidate_profile: CandidateProfessionalProfile) -> list[str]:
    return [employment.employer for employment in candidate_profile.employment_history]


def _audit_sensitive_text(text: str, path: str, findings: list[LinkedInProfileAuditFinding]) -> None:
    result = redact_sensitive_patterns(text)
    if result.redaction_count:
        _add_error(findings, path, "El texto contiene posibles datos sensibles.")


def _audit_numbers(
    text: str,
    path: str,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    source_text: str = context["source_text"]
    for number in _professional_numbers(text):
        if number not in source_text:
            _add_error(findings, path, f"La cifra '{number}' no esta respaldada por la evidencia del candidato.")


def _professional_numbers(text: str) -> set[str]:
    normalized = _normalize_for_match(text)
    numbers = set()
    for match in re.finditer(r"\b\d+(?:[.,]\d+)?%?\b", normalized):
        token = match.group(0)
        window = normalized[max(0, match.start() - 14) : match.end() + 14]
        if any(marker in window for marker in ("python", "iso", "sap", "s/4hana", "s4hana", "sql", "365")):
            continue
        numbers.add(token.replace(",", "."))
    return numbers


def _audit_market_only_terms(
    text: str,
    path: str,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    normalized = _normalize_for_match(text)
    for term in sorted(context["market_only_terms"]):
        if len(term) < 3:
            continue
        if _concept_found(term, normalized):
            _add_error(findings, path, "El texto usa una keyword o herramienta de mercado no respaldada como capacidad.")


def _audit_cliches(text: str, path: str, findings: list[LinkedInProfileAuditFinding]) -> None:
    normalized = _normalize_for_match(text)
    for cliche in PROFILE_CLICHES:
        if _normalize_for_match(cliche) in normalized:
            _add_warning(findings, path, f"Evita cliches o lenguaje inflado: {cliche}.")


def _audit_seniority_inflation(
    text: str,
    path: str,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    normalized = _normalize_for_match(text)
    if context["candidate_seniority"] in LOWER_SENIORITIES and any(term in normalized.split() for term in HIGH_SENIORITY_TERMS):
        _add_error(findings, path, "El texto parece elevar artificialmente el seniority del candidato.")


def _audit_included_keywords(
    keywords: list[str],
    text: str,
    path: str,
    context: dict[str, object],
    findings: list[LinkedInProfileAuditFinding],
    *,
    require_supported: bool = False,
) -> None:
    normalized = _normalize_for_match(text)
    for index, keyword in enumerate(keywords):
        key = _normalize_key(keyword)
        if not _concept_found(keyword, normalized):
            _add_error(findings, f"{path}[{index}]", "La keyword declarada no aparece en el texto.")
        in_market = key in context["market_keywords"] or any(_concept_found(keyword, term) for term in context["market_keywords"])
        in_candidate = _is_supported_keyword(key, keyword, context) or key in context["candidate_concept_keys"]
        if not in_market and not in_candidate:
            _add_error(findings, f"{path}[{index}]", "La keyword declarada no existe en mercado ni candidato.")
        if require_supported and not _is_supported_keyword(key, keyword, context):
            _add_error(findings, f"{path}[{index}]", "La keyword usada en contenido actual no esta respaldada por el candidato.")


def _audit_keyword_stuffing(text: str, path: str, findings: list[LinkedInProfileAuditFinding]) -> None:
    tokens = [token for token in _normalize_for_match(text).split() if len(token) > 4]
    counts = Counter(tokens)
    if any(count >= 8 for count in counts.values()):
        _add_warning(findings, path, "El texto parece tener keyword stuffing.")


def _audit_unknown_named_items(
    text: str,
    candidate_profile: CandidateProfessionalProfile,
    context: dict[str, object],
    path: str,
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    normalized = _normalize_for_match(text)
    for employer in context["employers"]:
        if employer and employer not in normalized:
            continue
    known_industries = {_normalize_key(value) for value in candidate_profile.industries}
    for industry in known_industries:
        if industry and industry in normalized:
            continue


def _audit_placements(
    placements: list[str],
    path: str,
    findings: list[LinkedInProfileAuditFinding],
) -> None:
    for index, placement in enumerate(placements):
        if _normalize_key(placement) not in ALLOWED_PLACEMENTS:
            _add_error(findings, f"{path}[{index}]", "La ubicacion recomendada no esta permitida.")


def _matching_employment(
    employer: str,
    source_role_title: str,
    employments: list[EmploymentEntry],
) -> EmploymentEntry | None:
    employer_key = _normalize_key(employer)
    role_key = _normalize_key(source_role_title)
    for employment in employments:
        if _normalize_key(employment.employer) == employer_key and _titles_correspond(employment.role_title, source_role_title):
            return employment
    for employment in employments:
        if _normalize_key(employment.employer) == employer_key or _normalize_key(employment.role_title) == role_key:
            return employment
    return None


def _inflates_role(source_title: str, suggested_title: str, context: dict[str, object]) -> bool:
    source = _normalize_for_match(source_title)
    suggested = _normalize_for_match(suggested_title)
    if any(term in suggested.split() for term in HIGH_SENIORITY_TERMS) and not any(
        term in source.split() for term in HIGH_SENIORITY_TERMS
    ):
        return context["candidate_seniority"] in LOWER_SENIORITIES
    return False


def _has_company_name(text: str, context: dict[str, object]) -> bool:
    normalized = _normalize_for_match(text)
    return any(company and company in normalized for company in context["companies"])


def _has_contact_data(text: str) -> bool:
    return bool(re.search(r"https?://|www\.|@|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text, flags=re.IGNORECASE))


def _is_supported_keyword(key: str, keyword: str, context: dict[str, object]) -> bool:
    return _term_supported(key, context["supported_concepts"], context["source_text"]) or _term_supported(
        _normalize_key(keyword),
        context["supported_concepts"],
        context["source_text"],
    )


def _term_supported(term: str, supported_concepts: set[str], source_text: str) -> bool:
    return any(_concept_found(term, concept) for concept in supported_concepts if concept) or _concept_found(term, source_text)


def _contains_any(text: str, values: list[str]) -> bool:
    normalized = _normalize_for_match(text)
    return any(_concept_found(value, normalized) for value in values)


def _concept_found(candidate: str, normalized_text: str) -> bool:
    normalized_candidate = _normalize_for_match(candidate)
    if not normalized_candidate:
        return False
    if normalized_candidate in normalized_text:
        return True
    tokens = [token for token in normalized_candidate.split() if len(token) > 2]
    if not tokens:
        return False
    text_tokens = set(normalized_text.split())
    matches = sum(1 for token in tokens if _token_matches(token, text_tokens))
    return matches >= max(1, min(len(tokens), 2)) and matches / len(tokens) >= 0.5


def _token_matches(candidate: str, text_tokens: set[str]) -> bool:
    if candidate in text_tokens:
        return True
    if len(candidate) < 5:
        return False
    stem = candidate[:5]
    return any(token.startswith(stem) or stem.startswith(token[:5]) for token in text_tokens if len(token) >= 5)


def _titles_correspond(expected: str, actual: str) -> bool:
    expected_tokens = {token for token in _normalize_for_match(expected).split() if len(token) > 2}
    actual_tokens = {token for token in _normalize_for_match(actual).split() if len(token) > 2}
    if not expected_tokens or not actual_tokens:
        return False
    overlap = expected_tokens & actual_tokens
    return bool(overlap) and len(overlap) / min(len(expected_tokens), len(actual_tokens)) >= 0.4


def _normalize_key(value: str) -> str:
    return _normalize_for_match(value)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    ascii_text = ascii_text.casefold()
    ascii_text = re.sub(r"[^\w+#./%]+", " ", ascii_text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _add_error(findings: list[LinkedInProfileAuditFinding], path: str, message: str) -> None:
    findings.append(LinkedInProfileAuditFinding(severity="error", path=path, message=message))


def _add_warning(findings: list[LinkedInProfileAuditFinding], path: str, message: str) -> None:
    findings.append(LinkedInProfileAuditFinding(severity="warning", path=path, message=message))
