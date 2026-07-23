"""Deterministic checks for target job market analysis."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from schemas.enums import PriorityLevel, SeniorityLevel
from schemas.input_models import JobInput
from schemas.job_analysis_models import JobAnalysisAuditFinding, JobAnalysisAuditResult
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis

REQUIRED_SIGNALS = (
    "required",
    "must",
    "mandatory",
    "indispensable",
    "requisito",
    "se requiere",
    "requiere",
    "requerido",
    "mínimo",
    "minimo",
    "essential",
    "indispensable",
)
DESIRABLE_SIGNALS = (
    "preferred",
    "desirable",
    "nice to have",
    "plus",
    "ideal",
    "deseable",
    "valorado",
)
EXECUTIVE_VALUES = {SeniorityLevel.DIRECTOR.value, SeniorityLevel.EXECUTIVE.value}
ENTRY_VALUES = {SeniorityLevel.ENTRY.value}


def audit_target_market_analysis(
    analysis: TargetMarketAnalysis,
    jobs: list[JobInput],
) -> JobAnalysisAuditResult:
    """Audit correspondence, evidence and consistency of a target market analysis."""
    findings: list[JobAnalysisAuditFinding] = []
    expected_indices = {job.index for job in jobs}
    job_by_index = {job.index: job for job in jobs}
    normalized_descriptions = {job.index: _normalize_for_match(job.description) for job in jobs}

    _audit_job_analysis_correspondence(analysis.job_analyses, job_by_index, expected_indices, findings)
    _audit_keywords(analysis.keywords, expected_indices, normalized_descriptions, findings)
    _audit_job_requirements(analysis.job_analyses, normalized_descriptions, findings)
    _audit_common_requirements(analysis.common_requirements, normalized_descriptions, findings)
    _audit_tools(analysis, normalized_descriptions, findings)
    _audit_common_responsibilities(analysis.common_responsibilities, normalized_descriptions, findings)
    _audit_consolidated_fields(analysis, jobs, findings)

    passed = not any(finding.severity == "error" for finding in findings)
    return JobAnalysisAuditResult(passed=passed, findings=findings)


def _audit_job_analysis_correspondence(
    job_analyses: list[JobAnalysis],
    job_by_index: dict[int, JobInput],
    expected_indices: set[int],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    actual_indices = [job_analysis.job_index for job_analysis in job_analyses]
    actual_set = set(actual_indices)
    if len(job_analyses) < 2 or len(job_analyses) > 6:
        _add_error(findings, "job_analyses", "El número de análisis individuales debe estar entre dos y seis.")
    if len(actual_indices) != len(actual_set):
        _add_error(findings, "job_analyses", "Los índices de análisis deben ser únicos.")
    for missing in sorted(expected_indices - actual_set):
        _add_error(findings, "job_analyses", f"Falta el análisis de la vacante {missing}.")
    for extra in sorted(actual_set - expected_indices):
        _add_error(findings, "job_analyses", f"Existe un análisis para una vacante no recibida: {extra}.")

    for index, job_analysis in enumerate(job_analyses):
        path = f"job_analyses[{index}]"
        job = job_by_index.get(job_analysis.job_index)
        if not job:
            continue
        if not _titles_correspond(job.title, job_analysis.title):
            _add_error(findings, f"{path}.title", "El título del análisis no corresponde razonablemente a la vacante.")
        if job.company and not _company_corresponds(job.company, job_analysis.company):
            _add_error(findings, f"{path}.company", "La empresa del análisis no corresponde a la vacante.")
        _audit_seniority(job.title, job.description, job_analysis.inferred_seniority, f"{path}.inferred_seniority", findings)
        if not job_analysis.role_summary.strip():
            _add_error(findings, f"{path}.role_summary", "El resumen del rol no puede estar vacío.")
        if not job_analysis.responsibilities:
            _add_warning(findings, f"{path}.responsibilities", "La vacante no incluye responsabilidades extraídas.")


def _audit_keywords(
    keywords: list[MarketKeyword],
    expected_indices: set[int],
    normalized_descriptions: dict[int, str],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    seen: set[str] = set()
    for index, keyword in enumerate(keywords):
        path = f"keywords[{index}]"
        normalized_keyword = _normalize_key(keyword.normalized_keyword)
        if not keyword.keyword.strip() or not keyword.normalized_keyword.strip():
            _add_error(findings, path, "La keyword y su versión normalizada no pueden estar vacías.")
        if normalized_keyword in seen:
            _add_error(findings, path, "Se detectó una keyword duplicada por normalized_keyword.")
        seen.add(normalized_keyword)
        unique_indices = set(keyword.job_indices)
        if keyword.frequency != len(unique_indices):
            _add_error(findings, path, "frequency debe ser igual al número de job_indices únicos.")
        if keyword.frequency < 1 or keyword.frequency > len(expected_indices):
            _add_error(findings, path, "frequency está fuera del rango de vacantes recibidas.")
        for job_index in unique_indices:
            if job_index not in expected_indices:
                _add_error(findings, path, f"La keyword referencia un índice inexistente: {job_index}.")
                continue
            if not _concept_found(keyword.keyword, keyword.normalized_keyword, normalized_descriptions[job_index]):
                _add_warning(findings, path, "La keyword no aparece razonablemente en una vacante referenciada.")
        for job_index, description in normalized_descriptions.items():
            if job_index not in unique_indices and _concept_found(keyword.keyword, keyword.normalized_keyword, description):
                _add_warning(findings, path, "La keyword parece aparecer en una vacante no incluida en job_indices.")
        if keyword.priority == PriorityLevel.LOW and keyword.frequency >= max(2, len(expected_indices) - 1):
            _add_warning(findings, path, "La prioridad parece baja para una keyword frecuente.")


def _audit_job_requirements(
    job_analyses: list[JobAnalysis],
    normalized_descriptions: dict[int, str],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    for job_index, job_analysis in enumerate(job_analyses):
        description = normalized_descriptions.get(job_analysis.job_index, "")
        seen: set[str] = set()
        for req_index, requirement in enumerate(job_analysis.requirements):
            path = f"job_analyses[{job_index}].requirements[{req_index}]"
            _audit_requirement(requirement, description, path, findings)
            key = _normalize_key(requirement.normalized_name)
            if key in seen:
                _add_error(findings, path, "Se detectó un requisito duplicado en la vacante.")
            seen.add(key)


def _audit_common_requirements(
    requirements: list[JobRequirement],
    normalized_descriptions: dict[int, str],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    seen: set[str] = set()
    for index, requirement in enumerate(requirements):
        path = f"common_requirements[{index}]"
        key = _normalize_key(requirement.normalized_name)
        if key in seen:
            _add_error(findings, path, "Se detectó un requisito común duplicado.")
        seen.add(key)
        support_count = _requirement_support_count(requirement, normalized_descriptions)
        if support_count < 2:
            _add_warning(findings, path, "Un requisito común debe estar respaldado por más de una vacante.")
        for keyword in requirement.exact_keywords:
            if _support_count(keyword, keyword, normalized_descriptions) == 0:
                _add_warning(findings, path, f"La keyword exacta del requisito no aparece en las vacantes: {keyword}.")


def _audit_requirement(
    requirement: JobRequirement,
    normalized_description: str,
    path: str,
    findings: list[JobAnalysisAuditFinding],
) -> None:
    if not _requirement_found(requirement, normalized_description):
        _add_warning(findings, path, "El requisito no está respaldado por la descripción de la vacante.")
    for keyword in requirement.exact_keywords:
        if not _concept_found(keyword, keyword, normalized_description):
            _add_warning(findings, path, f"La keyword exacta del requisito no aparece: {keyword}.")
    has_required_signal = _has_any_signal(normalized_description, REQUIRED_SIGNALS)
    has_desirable_signal = _has_any_signal(normalized_description, DESIRABLE_SIGNALS)
    if requirement.required and not has_required_signal:
        _add_warning(findings, path, "required=true exige lenguaje obligatorio razonable en la vacante.")
    if not requirement.required and has_required_signal and not has_desirable_signal:
        _add_warning(findings, path, "El requisito podría ser obligatorio según el lenguaje de la vacante.")


def _audit_tools(
    analysis: TargetMarketAnalysis,
    normalized_descriptions: dict[int, str],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    for index, tool in enumerate(analysis.tools_and_technologies):
        if _support_count(tool, tool, normalized_descriptions) == 0:
            _add_error(findings, f"tools_and_technologies[{index}]", "La herramienta o tecnología no aparece en las vacantes.")

    for job_index, job_analysis in enumerate(analysis.job_analyses):
        description = normalized_descriptions.get(job_analysis.job_index, "")
        for tool_index, tool in enumerate(job_analysis.tools_and_technologies):
            if not _concept_found(tool, tool, description):
                _add_error(
                    findings,
                    f"job_analyses[{job_index}].tools_and_technologies[{tool_index}]",
                    "La herramienta o tecnología no aparece en la vacante correspondiente.",
                )


def _audit_common_responsibilities(
    responsibilities: list[str],
    normalized_descriptions: dict[int, str],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    for index, responsibility in enumerate(responsibilities):
        if _support_count(responsibility, responsibility, normalized_descriptions) < 2:
            _add_warning(
                findings,
                f"common_responsibilities[{index}]",
                "Una responsabilidad común debe aparecer razonablemente en al menos dos vacantes.",
            )


def _audit_consolidated_fields(
    analysis: TargetMarketAnalysis,
    jobs: list[JobInput],
    findings: list[JobAnalysisAuditFinding],
) -> None:
    if not analysis.target_role_family.strip():
        _add_error(findings, "target_role_family", "La familia de roles no puede estar vacía.")
    title_sources = " ".join(job.title for job in jobs)
    for index, title in enumerate(analysis.suggested_target_titles):
        if not _titles_correspond(title_sources, title):
            _add_warning(findings, f"suggested_target_titles[{index}]", "El título sugerido no parece basarse en los títulos recibidos.")
    counts = Counter(str(job_analysis.inferred_seniority) for job_analysis in analysis.job_analyses)
    dominant = str(analysis.dominant_seniority)
    if counts and dominant != counts.most_common(1)[0][0]:
        _add_warning(findings, "dominant_seniority", "El seniority predominante no coincide con la mayoría de análisis individuales.")
    generic_differentiators = {"excelente oportunidad", "gran empresa", "beneficios", "ambiente dinamico"}
    for index, differentiator in enumerate(analysis.differentiators):
        if _normalize_key(differentiator) in generic_differentiators:
            _add_warning(findings, f"differentiators[{index}]", "El diferenciador parece genérico.")


def _audit_seniority(
    title: str,
    description: str,
    seniority: SeniorityLevel | str,
    path: str,
    findings: list[JobAnalysisAuditFinding],
) -> None:
    normalized = _normalize_for_match(f"{title} {description}")
    seniority_value = str(seniority.value if isinstance(seniority, SeniorityLevel) else seniority)
    if "intern" in normalized and seniority_value in EXECUTIVE_VALUES:
        _add_error(findings, path, "El seniority inferido es absurdo para una vacante Intern.")
    if "director" in normalized and seniority_value in ENTRY_VALUES:
        _add_error(findings, path, "El seniority inferido es absurdo para una vacante Director.")
    if seniority_value == SeniorityLevel.UNSPECIFIED.value and _has_any_signal(
        normalized,
        ("senior", "lead", "manager", "director", "executive", "junior", "entry"),
    ):
        _add_warning(findings, path, "La vacante contiene señales de seniority aunque se marcó unspecified.")


def _support_count(name: str, normalized_name: str, normalized_descriptions: dict[int, str]) -> int:
    return sum(
        1
        for description in normalized_descriptions.values()
        if _concept_found(name, normalized_name, description)
    )


def _requirement_support_count(requirement: JobRequirement, normalized_descriptions: dict[int, str]) -> int:
    return sum(1 for description in normalized_descriptions.values() if _requirement_found(requirement, description))


def _requirement_found(requirement: JobRequirement, normalized_description: str) -> bool:
    if _concept_found(requirement.name, requirement.normalized_name, normalized_description):
        return True
    return any(_concept_found(keyword, keyword, normalized_description) for keyword in requirement.exact_keywords)


def _concept_found(name: str, normalized_name: str, normalized_description: str) -> bool:
    candidates = [_normalize_for_match(name), _normalize_for_match(normalized_name)]
    return any(_phrase_or_tokens_found(candidate, normalized_description) for candidate in candidates if candidate)


def _phrase_or_tokens_found(candidate: str, normalized_description: str) -> bool:
    if candidate in normalized_description:
        return True
    tokens = [token for token in candidate.split() if len(token) > 2]
    if not tokens:
        return False
    description_tokens = set(normalized_description.split())
    matches = sum(1 for token in tokens if _token_matches(token, description_tokens))
    return matches >= max(1, min(len(tokens), 2)) and matches / len(tokens) >= 0.5


def _token_matches(candidate: str, description_tokens: set[str]) -> bool:
    if candidate in description_tokens or candidate in " ".join(description_tokens):
        return True
    if len(candidate) < 5:
        return False
    stem = candidate[:5]
    return any(token.startswith(stem) or stem.startswith(token[:5]) for token in description_tokens if len(token) >= 5)


def _titles_correspond(expected: str, actual: str) -> bool:
    expected_tokens = {token for token in _normalize_for_match(expected).split() if len(token) > 2}
    actual_tokens = {token for token in _normalize_for_match(actual).split() if len(token) > 2}
    if not expected_tokens or not actual_tokens:
        return False
    overlap = expected_tokens & actual_tokens
    return bool(overlap) and len(overlap) / min(len(expected_tokens), len(actual_tokens)) >= 0.4


def _company_corresponds(expected: str, actual: str | None) -> bool:
    if not actual:
        return False
    return _normalize_for_match(expected) == _normalize_for_match(actual)


def _has_any_signal(normalized_text: str, signals: tuple[str, ...]) -> bool:
    return any(_normalize_for_match(signal) in normalized_text for signal in signals)


def _normalize_key(value: str) -> str:
    return _normalize_for_match(value)


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    ascii_text = ascii_text.casefold()
    ascii_text = re.sub(r"[^\w+#.]+", " ", ascii_text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _add_error(findings: list[JobAnalysisAuditFinding], path: str, message: str) -> None:
    findings.append(JobAnalysisAuditFinding(severity="error", path=path, message=message))


def _add_warning(findings: list[JobAnalysisAuditFinding], path: str, message: str) -> None:
    findings.append(JobAnalysisAuditFinding(severity="warning", path=path, message=message))
