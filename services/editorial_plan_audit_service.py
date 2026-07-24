"""Local audit for LinkedIn professional brand editorial plans."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.editorial_plan_models import (
    EditorialPlanAuditFinding,
    EditorialPlanAuditResult,
    LinkedInPostFormat,
    ProfessionalBrandPlan,
)
from schemas.enums import EvidenceStatus, RequirementCoverage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis

_DATE_PATTERNS = (
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
)
_CLICKBAIT_PHRASES = (
    "no vas a creer",
    "lo que nadie te dice",
    "secreto que nadie",
    "la verdad que nadie",
    "esto cambiará tu vida",
    "this will change your life",
    "secret nobody",
)
_FORBIDDEN_CTA = (
    "dale like",
    "comparte",
    "sígueme",
    "sigueme",
    "follow me",
    "share this",
    "like this",
    "subscribe",
)
_PROFESSIONAL_CTA_MARKERS = ("?", "experiencia", "opinas", "resolverías", "resolverias", "cómo", "como", "what", "how")
_CONFIDENTIAL_PATTERNS = (
    r"\bcliente\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.-]+",
    r"\bclient\s+[A-Z][\w.-]+",
    r"\bpresupuesto\b|\bbudget\b|\b\$[0-9]",
    r"\bincidente confidencial\b|\bconfidential incident\b",
    r"\bvulnerabilidad\b|\bvulnerability\b|\bCVE-\d{4}-\d+\b",
    r"\bdato interno\b|\binternal data\b",
    r"\bNDA\b|\binformación protegida\b|\bprotected information\b",
)
_SENSITIVE_PATTERNS = (
    r"\bRFC\b",
    r"\bCURP\b",
    r"\bdomicilio particular\b",
    r"\bcuenta bancaria\b",
    r"\bcontrase(?:n|ñ)a\b",
)
_CLICHES = (
    "gurú",
    "guru",
    "ninja",
    "rockstar",
    "líder nato",
    "lider nato",
    "dar el 110%",
    "resultados garantizados",
    "disruptivo sin evidencia",
    "thought leader",
)
_INTERNAL_TERMS = ("request_id", "input_tokens", "output_tokens", "raw_response", "prompt", "api key", "openai")
_HASHTAG_RE = re.compile(r"^#[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_]{1,48}$")


def audit_editorial_plan(
    plan: ProfessionalBrandPlan,
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
) -> EditorialPlanAuditResult:
    """Validate an editorial plan against evidence, diversity, privacy and format rules."""
    findings: list[EditorialPlanAuditFinding] = []
    posts = plan.calendar.posts
    character_counts = {f"week{post.week}.{post.day}": len(post.body.strip()) for post in posts}
    _audit_structure(plan, findings)
    _audit_diversity(posts, findings)
    _audit_posts(posts, candidate_profile, market_analysis, compatibility_report, audit_report, findings)
    return EditorialPlanAuditResult(
        passed=not any(finding.severity == "error" for finding in findings),
        findings=findings,
        character_counts=character_counts,
    )


def editorial_plan_public_text(plan: ProfessionalBrandPlan) -> str:
    """Return all public editorial plan text for local checks."""
    values = [plan.summary, *plan.strengths_exploited, *plan.themes, *plan.risks, *plan.recommendations]
    for post in plan.calendar.posts:
        values.extend(
            [
                post.title,
                post.theme,
                post.audience,
                post.hook,
                post.body,
                post.cta,
                " ".join(post.hashtags),
                " ".join(post.keywords_used),
                " ".join(post.evidence_used),
                " ".join(post.claims_requiring_review),
                " ".join(post.notes),
            ]
        )
    return "\n".join(value for value in values if value)


def _audit_structure(plan: ProfessionalBrandPlan, findings: list[EditorialPlanAuditFinding]) -> None:
    posts = plan.calendar.posts
    if len(plan.calendar.weeks) != 4:
        _error(findings, "calendar.weeks", "El calendario debe contener exactamente 4 semanas.")
    if len(posts) != 12:
        _error(findings, "calendar.posts", "El plan debe contener exactamente 12 publicaciones.")
    formats = {post.format for post in posts}
    if len(formats) < 2:
        _error(findings, "calendar.posts.format", "El plan debe mezclar formatos corto, medio o largo.")


def _audit_diversity(posts: list[object], findings: list[EditorialPlanAuditFinding]) -> None:
    hooks = Counter(_norm(post.hook) for post in posts)
    ctas = Counter(_norm(post.cta) for post in posts)
    hashtag_sets = Counter(tuple(sorted(_norm(tag) for tag in post.hashtags)) for post in posts)
    for index, (previous, current) in enumerate(zip(posts, posts[1:]), start=2):
        if _norm(previous.theme) == _norm(current.theme):
            _error(findings, f"calendar.posts[{index}].theme", "No puede haber dos publicaciones consecutivas del mismo tema.")
    for hook, count in hooks.items():
        if hook and count > 1:
            _error(findings, "calendar.posts.hook", "No se debe repetir el mismo hook.")
    for cta, count in ctas.items():
        if cta and count > 1:
            _error(findings, "calendar.posts.cta", "No se debe repetir el mismo CTA.")
    for hashtag_set, count in hashtag_sets.items():
        if hashtag_set and count > 1:
            _warning(findings, "calendar.posts.hashtags", "Hay sets de hashtags repetidos; diversifica el enfoque.")


def _audit_posts(
    posts: list[object],
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
    findings: list[EditorialPlanAuditFinding],
) -> None:
    source_text = _source_text(candidate_profile, market_analysis, compatibility_report, audit_report)
    supported_terms = {_norm(term) for term in _supported_terms(candidate_profile, market_analysis, compatibility_report, audit_report)}
    unsupported_market_terms = {_norm(term) for term in _unsupported_market_terms(candidate_profile, market_analysis, compatibility_report)}
    allowed_hashtags = {_hashtag_key(term) for term in supported_terms if term}
    allowed_hashtags.update(
        {
            "liderazgo",
            "leadership",
            "networking",
            "aprendizaje",
            "learning",
            "metodologia",
            "methodology",
            "innovacion",
            "innovation",
            "tecnologia",
            "technology",
            "gestiondeproyectos",
            "projectmanagement",
            "comunicacion",
            "communication",
            "stakeholders",
            "agile",
            "jira",
        }
    )

    for index, post in enumerate(posts):
        path = f"calendar.posts[{index}]"
        _audit_length(post, path, findings)
        _audit_hook(post.hook, f"{path}.hook", findings)
        _audit_cta(post.cta, f"{path}.cta", findings)
        _audit_hashtags(post.hashtags, allowed_hashtags, f"{path}.hashtags", findings)
        _audit_evidence(post, source_text, supported_terms, unsupported_market_terms, path, findings)
        _audit_text_safety(post, path, findings)


def _audit_length(post: object, path: str, findings: list[EditorialPlanAuditFinding]) -> None:
    length = len(post.body.strip())
    if post.character_count != length:
        _error(findings, f"{path}.character_count", "El conteo declarado no coincide con el texto local.")
    ranges = {
        LinkedInPostFormat.SHORT.value: (300, 600),
        LinkedInPostFormat.MEDIUM.value: (600, 1200),
        LinkedInPostFormat.LONG.value: (1200, 2200),
    }
    minimum, maximum = ranges.get(str(post.format), (300, 2200))
    if length < minimum or length > maximum:
        _error(findings, f"{path}.body", f"La publicación {post.format} debe tener entre {minimum} y {maximum} caracteres.")


def _audit_hook(hook: str, path: str, findings: list[EditorialPlanAuditFinding]) -> None:
    lowered = _norm(hook)
    if not hook.strip():
        _error(findings, path, "Cada publicación debe tener hook.")
    if any(phrase in lowered for phrase in _CLICKBAIT_PHRASES):
        _error(findings, path, "El hook parece clickbait.")
    if len(hook.strip()) < 12:
        _error(findings, path, "El hook es demasiado corto para abrir una publicación profesional.")


def _audit_cta(cta: str, path: str, findings: list[EditorialPlanAuditFinding]) -> None:
    lowered = _norm(cta)
    if any(phrase in lowered for phrase in _FORBIDDEN_CTA):
        _error(findings, path, "El CTA no debe pedir likes, shares, follows ni suscripciones.")
    if not any(marker in lowered or marker in cta for marker in _PROFESSIONAL_CTA_MARKERS):
        _warning(findings, path, "El CTA debería abrir conversación profesional.")


def _audit_hashtags(
    hashtags: list[str],
    allowed_hashtags: set[str],
    path: str,
    findings: list[EditorialPlanAuditFinding],
) -> None:
    if len(hashtags) > 5:
        _error(findings, path, "Cada publicación puede tener máximo 5 hashtags.")
    normalized = [_hashtag_key(tag) for tag in hashtags]
    if len(normalized) != len(set(normalized)):
        _error(findings, path, "No repitas hashtags dentro de una publicación.")
    for tag, key in zip(hashtags, normalized):
        if not _HASHTAG_RE.match(tag):
            _error(findings, path, f"Hashtag inválido: {tag}.")
        if key and key not in allowed_hashtags:
            _warning(findings, path, f"Hashtag no aparece claramente relacionado con evidencia o mercado: {tag}.")


def _audit_evidence(
    post: object,
    source_text: str,
    supported_terms: set[str],
    unsupported_market_terms: set[str],
    path: str,
    findings: list[EditorialPlanAuditFinding],
) -> None:
    text = _norm("\n".join([post.title, post.theme, post.hook, post.body, post.cta, " ".join(post.keywords_used)]))
    for evidence in post.evidence_used:
        if not _phrase_has_support(evidence, source_text):
            _warning(findings, f"{path}.evidence_used", "Una evidencia usada no aparece claramente en los insumos estructurados.")
    for keyword in post.keywords_used:
        normalized = _norm(keyword)
        if normalized and normalized not in supported_terms and not any(normalized in term or term in normalized for term in supported_terms):
            _warning(findings, f"{path}.keywords_used", "Una keyword no aparece claramente respaldada por perfil, mercado o auditoría.")
    for term in unsupported_market_terms:
        if term and term in text and not any(marker in text for marker in ("aprendizaje", "preparar", "brecha", "fortalecer", "learning", "gap")):
            _error(findings, f"{path}.body", "Un requisito o keyword faltante aparece como experiencia demostrada.")


def _audit_text_safety(post: object, path: str, findings: list[EditorialPlanAuditFinding]) -> None:
    text = "\n".join([post.title, post.hook, post.body, post.cta, " ".join(post.hashtags), " ".join(post.notes)])
    lowered = _norm(text)
    for pattern in _CONFIDENTIAL_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            _error(findings, path, "La publicación contiene información potencialmente confidencial o protegida.")
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            _error(findings, path, "La publicación contiene información sensible no permitida.")
    for cliché in _CLICHES:
        if _norm(cliché) in lowered:
            _warning(findings, path, f"Evita cliché o exageración: {cliché}.")
    for term in _INTERNAL_TERMS:
        if term in lowered:
            _error(findings, path, f"La publicación contiene marcador interno no permitido: {term}.")
    for pattern in _DATE_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            _warning(findings, path, "Revisa fechas absolutas; el calendario no debe depender de fechas concretas.")


def _supported_terms(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
) -> Iterable[str]:
    yield candidate_profile.professional_identity
    yield from candidate_profile.targetable_roles
    yield from candidate_profile.industries
    for skill in candidate_profile.skills:
        if _evidence_value(skill.evidence_status) == EvidenceStatus.SUPPORTED.value:
            yield skill.name
            yield skill.normalized_name
    for entry in candidate_profile.employment_history:
        yield entry.role_title
        yield from entry.industries
        for responsibility in entry.responsibilities:
            if _evidence_value(responsibility.status) == EvidenceStatus.SUPPORTED.value:
                yield responsibility.statement
        for achievement in entry.achievements:
            if _evidence_value(achievement.evidence_status) == EvidenceStatus.SUPPORTED.value:
                yield achievement.description
                yield achievement.measurable_result or ""
        for skill in entry.technologies:
            if _evidence_value(skill.evidence_status) == EvidenceStatus.SUPPORTED.value:
                yield skill.name
                yield skill.normalized_name
    for keyword in market_analysis.keywords:
        yield keyword.keyword
        yield keyword.normalized_keyword
    yield from market_analysis.technical_skills
    yield from market_analysis.leadership_skills
    yield from market_analysis.business_skills
    yield from market_analysis.tools_and_technologies
    yield from market_analysis.industries
    for job in compatibility_report.job_compatibilities:
        yield from job.strengths
        for match in job.requirement_matches:
            if _evidence_value(match.evidence_status) == EvidenceStatus.SUPPORTED.value and _coverage_value(match.coverage) in {
                RequirementCoverage.FULL.value,
                RequirementCoverage.PARTIAL.value,
                RequirementCoverage.INDIRECT.value,
            }:
                yield match.requirement_name
                yield match.normalized_requirement
                yield from match.matched_candidate_items
    yield from compatibility_report.common_strengths
    if audit_report.linkedin_positioning:
        for finding in [*audit_report.linkedin_positioning.strengths, *audit_report.linkedin_positioning.findings]:
            yield finding.title
            yield from finding.evidence
    if audit_report.ats_estimation:
        yield from audit_report.ats_estimation.matched_keywords


def _unsupported_market_terms(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
) -> Iterable[str]:
    supported_text = _norm(candidate_profile.model_dump_json())
    for keyword in market_analysis.keywords:
        key = _norm(keyword.keyword)
        if key and key not in supported_text:
            yield keyword.keyword
    for job in compatibility_report.job_compatibilities:
        yield from job.critical_gaps
        yield from job.other_gaps
        for match in job.requirement_matches:
            if _coverage_value(match.coverage) == RequirementCoverage.MISSING.value:
                yield match.requirement_name
                yield from match.missing_elements


def _source_text(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
) -> str:
    payload = {
        "candidate_profile": candidate_profile.model_dump(mode="json"),
        "market_analysis": market_analysis.model_dump(mode="json"),
        "compatibility_report": compatibility_report.model_dump(mode="json"),
        "audit_report": audit_report.model_dump(mode="json"),
    }
    return _norm(json.dumps(payload, ensure_ascii=False))


def _phrase_has_support(phrase: str, source_text: str) -> bool:
    tokens = [token for token in _norm(phrase).split() if len(token) >= 4]
    if not tokens:
        return False
    hits = sum(1 for token in set(tokens) if token in source_text)
    return hits / max(1, len(set(tokens))) >= 0.35


def _hashtag_key(value: str) -> str:
    normalized = _norm(str(value).lstrip("#"))
    return normalized.replace(" ", "")


def _evidence_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _coverage_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _error(findings: list[EditorialPlanAuditFinding], path: str, message: str) -> None:
    findings.append(EditorialPlanAuditFinding(severity="error", path=path, message=message))


def _warning(findings: list[EditorialPlanAuditFinding], path: str, message: str) -> None:
    findings.append(EditorialPlanAuditFinding(severity="warning", path=path, message=message))


def _norm(value: object) -> str:
    text = str(value or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^\w+#./%]+", " ", ascii_text, flags=re.UNICODE).strip()
