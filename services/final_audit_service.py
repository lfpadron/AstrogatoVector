"""Local final audit for LinkedIn positioning and ATS readiness."""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from schemas.audit_models import (
    ATS_AUDIT_COMPONENT_WEIGHTS,
    FINAL_AUDIT_DISCLAIMER,
    FINAL_AUDIT_METHODOLOGY_VERSION,
    FINAL_AUDIT_PROMPT_VERSION,
    LINKEDIN_AUDIT_COMPONENT_WEIGHTS,
    ATSAudit,
    AuditFinding,
    AuditRecommendation,
    AuditReport,
    AuditScoreComponent,
    LinkedInPositioningAudit,
    score_label_for_score,
)
from schemas.compatibility_models import CompatibilityReport, RequirementMatch
from schemas.enums import EvidenceStatus, PriorityLevel, RequirementCoverage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import MarketKeyword, TargetMarketAnalysis
from schemas.profile_models import LinkedInProfileOutput
from services.final_audit_validation_service import audit_final_report

StatusCallback = Callable[[str], None]

FINAL_AUDIT_SUCCESS_MESSAGE = (
    "La auditoría integral de LinkedIn y ATS fue calculada y validada correctamente."
)
FINAL_AUDIT_MISSING_STAGES_MESSAGE = (
    "Para auditar el posicionamiento se necesita un perfil profesional válido, un mercado válido, "
    "un perfil de LinkedIn generado y un reporte de compatibilidad válido."
)
FINAL_AUDIT_INVALID_MESSAGE = (
    "No fue posible validar la auditoría integral generada localmente. No se mostraron resultados parciales."
)


@dataclass(frozen=True)
class AuditContext:
    """Prepared normalized data used by the deterministic audit."""

    visible_text: str
    visible_text_normalized: str
    headline_normalized: str
    about_normalized: str
    experience_normalized: str
    banner_normalized: str
    supported_terms: set[str]
    candidate_terms: set[str]
    market_keywords: list[MarketKeyword]
    important_keywords: list[MarketKeyword]
    supported_market_keywords: list[MarketKeyword]
    unsupported_market_keywords: list[MarketKeyword]
    selected_skill_keys: set[str]
    ats_keyword_keys: set[str]
    compatibility_strength_terms: set[str]


class FinalAuditService:
    """Build a final explainable LinkedIn and ATS audit without sending sources externally."""

    def generate_report(
        self,
        candidate_profile: CandidateProfessionalProfile,
        market_analysis: TargetMarketAnalysis,
        linkedin_profile: LinkedInProfileOutput,
        compatibility_report: CompatibilityReport,
        *,
        status_callback: StatusCallback | None = None,
    ) -> AuditReport:
        """Generate and locally validate the final audit report."""
        start_time = time.perf_counter()
        try:
            if status_callback:
                status_callback("Preparando auditoría final...")
            context = _build_context(candidate_profile, market_analysis, linkedin_profile, compatibility_report)

            if status_callback:
                status_callback("Evaluando posicionamiento de LinkedIn...")
            linkedin_audit = _build_linkedin_audit(candidate_profile, market_analysis, linkedin_profile, context)

            if status_callback:
                status_callback("Evaluando lectura ATS...")
            ats_audit = _build_ats_audit(market_analysis, linkedin_profile, compatibility_report, context)

            report = AuditReport(
                success=True,
                linkedin_positioning=linkedin_audit,
                ats_estimation=ats_audit,
                average_compatibility_score=compatibility_report.average_compatibility_score,
                latency_ms=_elapsed_ms(start_time),
                audit_passed=True,
                prompt_version=FINAL_AUDIT_PROMPT_VERSION,
                methodology_version=FINAL_AUDIT_METHODOLOGY_VERSION,
            )

            if status_callback:
                status_callback("Validando hallazgos y scores...")
            validation = audit_final_report(report)
            audit_findings = _format_validation_findings(validation.findings)
            if not validation.passed:
                return AuditReport(
                    success=False,
                    latency_ms=_elapsed_ms(start_time),
                    audit_passed=False,
                    audit_findings=audit_findings,
                    error_category="final_audit_validation_failed",
                    user_message=FINAL_AUDIT_INVALID_MESSAGE,
                    retryable=False,
                    prompt_version=FINAL_AUDIT_PROMPT_VERSION,
                    methodology_version=FINAL_AUDIT_METHODOLOGY_VERSION,
                )
            return report.model_copy(update={"audit_findings": audit_findings})
        except (ValueError, ValidationError):
            return AuditReport(
                success=False,
                latency_ms=_elapsed_ms(start_time),
                audit_passed=False,
                error_category="final_audit_failed",
                user_message=FINAL_AUDIT_INVALID_MESSAGE,
                retryable=False,
                prompt_version=FINAL_AUDIT_PROMPT_VERSION,
                methodology_version=FINAL_AUDIT_METHODOLOGY_VERSION,
            )


def build_final_audit_fingerprint(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    compatibility_report: CompatibilityReport,
    *,
    prompt_version: str = FINAL_AUDIT_PROMPT_VERSION,
    methodology_version: str = FINAL_AUDIT_METHODOLOGY_VERSION,
) -> str:
    """Build a stable local fingerprint for final audit reuse."""
    hasher = hashlib.sha256()
    for value in (
        prompt_version,
        methodology_version,
        _stable_json(candidate_profile),
        _stable_json(market_analysis),
        _stable_json(linkedin_profile),
        _stable_json(compatibility_report),
    ):
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _build_linkedin_audit(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
) -> LinkedInPositioningAudit:
    findings: list[AuditFinding] = []
    strengths: list[AuditFinding] = []
    risks: list[AuditFinding] = []

    headline_score = _audit_headline(linkedin_profile, context, findings, strengths)
    about_score = _audit_about(candidate_profile, market_analysis, linkedin_profile, context, findings, strengths, risks)
    experience_score = _audit_experience(candidate_profile, linkedin_profile, context, findings, strengths, risks)
    skills_score = _audit_linkedin_skills(linkedin_profile, context, findings, strengths, risks)
    banner_score = _audit_banner(linkedin_profile, context, findings, strengths)
    readability_score = _audit_readability(linkedin_profile, context, findings, strengths)

    components = [
        _component("Headline", LINKEDIN_AUDIT_COMPONENT_WEIGHTS["Headline"], headline_score, "Claridad, longitud y keyword principal del titular."),
        _component("About", LINKEDIN_AUDIT_COMPONENT_WEIGHTS["About"], about_score, "Profundidad, credibilidad y alineación del About."),
        _component("Experience", LINKEDIN_AUDIT_COMPONENT_WEIGHTS["Experience"], experience_score, "Consistencia y especificidad de experiencia reescrita."),
        _component("Skills", LINKEDIN_AUDIT_COMPONENT_WEIGHTS["Skills"], skills_score, "Priorización de skills respaldadas y relevantes."),
        _component("Banner", LINKEDIN_AUDIT_COMPONENT_WEIGHTS["Banner"], banner_score, "Propuesta de valor y limpieza del banner textual."),
        _component("Readability", LINKEDIN_AUDIT_COMPONENT_WEIGHTS["Readability"], readability_score, "Legibilidad y ausencia de saturación de palabras clave."),
    ]
    score = _weighted_component_score(components)
    recommendations = _recommendations_from_findings([*findings, *risks])
    return LinkedInPositioningAudit(
        score=score,
        score_label=score_label_for_score(score),
        components=components,
        findings=_dedupe_findings(findings),
        strengths=_dedupe_findings(strengths),
        risks=_dedupe_findings(risks),
        quick_wins=[recommendation for recommendation in recommendations if recommendation.priority == "Quick Wins"],
        recommendations=recommendations,
        disclaimer=FINAL_AUDIT_DISCLAIMER,
    )


def _build_ats_audit(
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    compatibility_report: CompatibilityReport,
    context: AuditContext,
) -> ATSAudit:
    findings: list[AuditFinding] = []
    strengths: list[AuditFinding] = []
    risks: list[AuditFinding] = []

    matched_keywords, missing_keywords = _keyword_coverage(context)
    keyword_score = _audit_keyword_coverage(matched_keywords, missing_keywords, context, findings, strengths, risks)
    requirement_score = _audit_requirement_coverage(compatibility_report, findings, strengths, risks)
    skills_score = _audit_ats_skills(linkedin_profile, context, findings, strengths, risks)
    experience_score = _audit_ats_experience(linkedin_profile, compatibility_report, context, findings, strengths, risks)
    title_score = _audit_titles(market_analysis, linkedin_profile, context, findings, strengths, risks)
    consistency_score = _audit_ats_consistency(linkedin_profile, context, findings, strengths, risks)

    components = [
        _component(
            "Cobertura keywords",
            ATS_AUDIT_COMPONENT_WEIGHTS["Cobertura keywords"],
            keyword_score,
            "Cobertura visible de keywords prioritarias y respaldadas.",
        ),
        _component(
            "Cobertura requisitos",
            ATS_AUDIT_COMPONENT_WEIGHTS["Cobertura requisitos"],
            requirement_score,
            "Cobertura de requisitos calculada desde el reporte de compatibilidad.",
        ),
        _component("Skills", ATS_AUDIT_COMPONENT_WEIGHTS["Skills"], skills_score, "Skills seleccionadas y alineadas con el mercado."),
        _component("Experiencia", ATS_AUDIT_COMPONENT_WEIGHTS["Experiencia"], experience_score, "Evidencia de experiencia reflejada en textos visibles."),
        _component("Títulos", ATS_AUDIT_COMPONENT_WEIGHTS["Títulos"], title_score, "Alineación de títulos con roles objetivo."),
        _component("Consistencia", ATS_AUDIT_COMPONENT_WEIGHTS["Consistencia"], consistency_score, "Separación entre brechas y capacidades respaldadas."),
    ]
    score = _weighted_component_score(components)
    recommendations = _recommendations_from_findings([*findings, *risks])
    return ATSAudit(
        score=score,
        score_label=score_label_for_score(score),
        components=components,
        matched_keywords=[keyword.keyword for keyword in matched_keywords],
        missing_keywords=[keyword.keyword for keyword in missing_keywords],
        findings=_dedupe_findings(findings),
        strengths=_dedupe_findings(strengths),
        risks=_dedupe_findings(risks),
        quick_wins=[recommendation for recommendation in recommendations if recommendation.priority == "Quick Wins"],
        recommendations=recommendations,
        disclaimer=FINAL_AUDIT_DISCLAIMER,
    )


def _audit_headline(
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
) -> float:
    score = 100.0
    headline = linkedin_profile.headline.text.strip()
    headline_length = len(headline)
    top_keyword = context.important_keywords[0].keyword if context.important_keywords else None

    if headline_length > 220:
        score -= 30
        findings.append(
            _finding(
                "high",
                "Headline",
                "Headline demasiado largo",
                "El headline supera el máximo recomendado por LinkedIn.",
                "Puede cortarse visualmente y reducir claridad para reclutadores.",
                "Reducir el headline a 220 caracteres o menos conservando rol objetivo y una keyword respaldada.",
                [f"{headline_length} caracteres"],
                "Quick Wins",
            )
        )
    elif headline_length < 45:
        score -= 10
        findings.append(
            _finding(
                "low",
                "Headline",
                "Headline breve",
                "El headline comunica poco contexto de especialidad.",
                "Puede desaprovechar espacio para keywords relevantes.",
                "Agregar una especialidad respaldada del mercado al headline.",
                [headline],
                "Quick Wins",
            )
        )
    if top_keyword and not _contains(top_keyword, context.headline_normalized):
        score -= 18
        findings.append(
            _finding(
                "medium",
                "Headline",
                "Keyword principal ausente",
                f"La keyword prioritaria '{top_keyword}' no aparece en el headline.",
                "Reduce alineación inmediata con búsquedas y lectura de reclutadores.",
                f"Incluir '{top_keyword}' en el headline si refleja experiencia respaldada.",
                [f"Keyword prioritaria: {top_keyword}"],
                "Quick Wins",
            )
        )
    if _is_generic_headline(headline):
        score -= 12
        findings.append(
            _finding(
                "medium",
                "Headline",
                "Headline demasiado genérico",
                "El headline se apoya casi solo en el cargo y no comunica diferenciador.",
                "Puede competir mal contra perfiles con especialidad explícita.",
                "Agregar una línea de especialidad respaldada, por ejemplo herramienta, industria o responsabilidad frecuente.",
                [headline],
                "Quick Wins",
            )
        )
    if score >= 85:
        strengths.append(
            _finding(
                "info",
                "Headline",
                "Headline claro",
                "El headline comunica rol objetivo y keywords relevantes sin exceder longitud.",
                "Facilita lectura rápida y búsqueda por términos del mercado.",
                "Mantener esta estructura y revisar solo si cambia el mercado objetivo.",
                [headline],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_about(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    score = 100.0
    about = linkedin_profile.about.text.strip()
    about_length = len(about)
    if about_length < 700:
        score -= 20
        findings.append(
            _finding(
                "medium",
                "About",
                "About demasiado corto",
                "El About no aprovecha suficiente espacio para propuesta de valor, evidencia y mercado.",
                "Puede quedar débil ante reclutadores y sistemas que ponderan contexto profesional.",
                "Expandir el About con responsabilidades y logros respaldados del perfil profesional.",
                [f"{about_length} caracteres"],
                "Medium Effort",
            )
        )
    elif about_length > 2600:
        score -= 10
        findings.append(
            _finding(
                "low",
                "About",
                "About demasiado largo",
                "El About se acerca al límite alto recomendado.",
                "Puede perder foco y reducir legibilidad.",
                "Reducir repeticiones y conservar solo evidencia directamente alineada con el mercado.",
                [f"{about_length} caracteres"],
                "Medium Effort",
            )
        )
    if not _has_first_person(about):
        score -= 8
        findings.append(
            _finding(
                "low",
                "About",
                "About poco personal",
                "El About no parece estar escrito en primera persona.",
                "Puede sonar menos humano y menos natural para LinkedIn.",
                "Reescribir la apertura en primera persona sin inventar experiencia.",
                [about[:180]],
                "Quick Wins",
            )
        )
    industry_visible = any(_contains(industry, context.about_normalized) for industry in candidate_profile.industries + market_analysis.industries)
    if (candidate_profile.industries or market_analysis.industries) and not industry_visible:
        score -= 8
        risks.append(
            _finding(
                "medium",
                "Market Alignment",
                "Industria poco visible",
                "La industria objetivo aparece en la evidencia o el mercado, pero no queda clara en el About.",
                "Puede reducir alineación percibida con vacantes sectoriales.",
                "Mencionar la industria respaldada en el About usando una frase de contexto profesional.",
                [", ".join(candidate_profile.industries + market_analysis.industries)],
                "Quick Wins",
            )
        )
    if _contains_any(["liderazgo", "leadership", "stakeholder", "equipo", "teams"], context.about_normalized):
        strengths.append(
            _finding(
                "info",
                "Leadership",
                "Liderazgo visible",
                "El About incluye señales de liderazgo o coordinación alineadas con el mercado.",
                "Refuerza credibilidad para roles con gestión de stakeholders o equipos.",
                "Conservar las menciones de liderazgo que estén respaldadas por evidencia.",
                ["About"],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_experience(
    candidate_profile: CandidateProfessionalProfile,
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    score = 100.0
    if len(linkedin_profile.experience) != len(candidate_profile.employment_history):
        score -= 25
        findings.append(
            _finding(
                "high",
                "Experience",
                "Experiencia inconsistente",
                "La experiencia reescrita no tiene una entrada por cada empleo fuente.",
                "Puede omitir evidencia relevante o crear dudas sobre continuidad profesional.",
                "Revisar que cada empleo fuente tenga exactamente una experiencia reescrita.",
                [f"Fuente: {len(candidate_profile.employment_history)}; salida: {len(linkedin_profile.experience)}"],
                "Medium Effort",
            )
        )
    short_entries = [entry.employer for entry in linkedin_profile.experience if len(entry.rewritten_text) < 120]
    if short_entries:
        score -= min(20, len(short_entries) * 8)
        risks.append(
            _finding(
                "medium",
                "Experience",
                "Experiencia poco específica",
                "Algunas experiencias tienen descripciones demasiado breves.",
                "Puede reducir evidencia visible de responsabilidades y logros.",
                "Ampliar cada experiencia breve con responsabilidades respaldadas y resultados verificables.",
                short_entries,
                "Medium Effort",
            )
        )
    reflected_strengths = sum(1 for term in context.compatibility_strength_terms if _contains(term, context.experience_normalized))
    if context.compatibility_strength_terms and reflected_strengths == 0:
        score -= 10
        findings.append(
            _finding(
                "medium",
                "Market Alignment",
                "Compatibilidad alta no reflejada en experiencia",
                "Las fortalezas del reporte de compatibilidad no aparecen claramente en la experiencia reescrita.",
                "Se pierde una oportunidad de reforzar evidencia donde ATS y reclutadores suelen buscar contexto.",
                "Incorporar fortalezas respaldadas de compatibilidad en la experiencia correspondiente.",
                sorted(context.compatibility_strength_terms)[:4],
                "Medium Effort",
            )
        )
    if score >= 82 and linkedin_profile.experience:
        strengths.append(
            _finding(
                "info",
                "Experience",
                "Experiencia sólida",
                "La experiencia reescrita mantiene correspondencia con empleos fuente y suficiente especificidad.",
                "Refuerza credibilidad y trazabilidad.",
                "Mantener el contenido y revisar manualmente tono y cifras antes de publicar.",
                [entry.employer for entry in linkedin_profile.experience[:3]],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_linkedin_skills(
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    score = 100.0
    names = [_normalize(skill.name) for skill in linkedin_profile.prioritized_skills]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    if duplicates:
        score -= 18
        findings.append(
            _finding(
                "medium",
                "Skills",
                "Skills duplicadas",
                "La lista de skills priorizadas contiene duplicados o variantes equivalentes.",
                "Puede desperdiciar espacio de skills y reducir claridad.",
                "Unificar variantes y conservar la denominación más reconocible en el mercado.",
                duplicates,
                "Quick Wins",
            )
        )
    missing_supported = [
        keyword.keyword
        for keyword in context.supported_market_keywords[:5]
        if _normalize(keyword.keyword) not in names and _normalize(keyword.normalized_keyword) not in names
    ]
    if missing_supported:
        score -= min(25, len(missing_supported) * 7)
        risks.append(
            _finding(
                "medium",
                "Skills",
                "Skills respaldadas ausentes",
                "Hay keywords importantes del mercado respaldadas por el candidato que no aparecen en skills priorizadas.",
                "Puede bajar la alineación visible del perfil.",
                f"Agregar {', '.join(missing_supported[:3])} a skills si se mantiene evidencia respaldada.",
                missing_supported[:5],
                "Quick Wins",
            )
        )
    if len(linkedin_profile.prioritized_skills) >= 3 and not duplicates:
        strengths.append(
            _finding(
                "info",
                "Skills",
                "Skills bien priorizadas",
                "La sección de skills incluye varias capacidades respaldadas y ordenadas.",
                "Ayuda a orientar lectura humana y búsqueda por términos.",
                "Conservar el orden mientras las prioridades de mercado no cambien.",
                [skill.name for skill in linkedin_profile.prioritized_skills[:5]],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_banner(
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
) -> float:
    score = 100.0
    banner = linkedin_profile.banner
    specialties = _split_specialties(banner.specialty_line)
    if len(specialties) > 5:
        score -= 15
        findings.append(
            _finding(
                "low",
                "Banner",
                "Banner con demasiadas especialidades",
                "La línea de especialidades lista más de cinco elementos.",
                "Puede verse saturada y menos memorable.",
                "Conservar tres a cinco especialidades prioritarias y respaldadas.",
                specialties,
                "Quick Wins",
            )
        )
    if len(banner.primary_line.strip()) < 18 or _is_generic_headline(banner.primary_line):
        score -= 18
        findings.append(
            _finding(
                "medium",
                "Banner",
                "Banner sin propuesta de valor clara",
                "La línea principal del banner no comunica una propuesta profesional concreta.",
                "Reduce el impacto visual del primer vistazo.",
                "Reformular la línea principal con rol objetivo y resultado o especialidad respaldada.",
                [banner.primary_line],
                "Quick Wins",
            )
        )
    if score >= 85:
        strengths.append(
            _finding(
                "info",
                "Banner",
                "Banner profesional",
                "El banner mantiene una propuesta clara y una cantidad razonable de especialidades.",
                "Aporta consistencia visual sin saturar.",
                "Mantener el enfoque y regenerar el PNG si editas el texto.",
                [banner.primary_line, banner.specialty_line],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_readability(
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
) -> float:
    score = 100.0
    long_sentences = [sentence for sentence in _sentences(linkedin_profile.about.text) if len(sentence) > 260]
    if long_sentences:
        score -= 12
        findings.append(
            _finding(
                "low",
                "Readability",
                "Oraciones demasiado largas",
                "El About contiene oraciones extensas que dificultan lectura rápida.",
                "Puede reducir claridad en móvil y en revisión rápida.",
                "Dividir oraciones largas en frases más cortas conservando evidencia.",
                [long_sentences[0][:220]],
                "Quick Wins",
            )
        )
    stuffing_terms = _keyword_stuffing_terms(context.visible_text_normalized)
    if stuffing_terms:
        score -= 18
        findings.append(
            _finding(
                "medium",
                "Keywords",
                "Keyword stuffing",
                "Algunas palabras clave aparecen con frecuencia excesiva.",
                "Puede sonar forzado y restar credibilidad.",
                "Reducir repeticiones y dejar keywords solo donde aporten contexto.",
                stuffing_terms[:5],
                "Quick Wins",
            )
        )
    if score >= 88:
        strengths.append(
            _finding(
                "info",
                "Readability",
                "Buena legibilidad",
                "El perfil no muestra señales fuertes de saturación o frases excesivamente largas.",
                "Facilita lectura humana y revisión en móvil.",
                "Mantener párrafos breves y lenguaje directo.",
                ["About y experiencia"],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_keyword_coverage(
    matched_keywords: list[MarketKeyword],
    missing_keywords: list[MarketKeyword],
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    total = len(context.supported_market_keywords) or len(context.important_keywords)
    if total == 0:
        return 75.0
    score = round((len(matched_keywords) / total) * 100, 1)
    if score >= 80:
        strengths.append(
            _finding(
                "info",
                "ATS",
                "Excelente cobertura ATS",
                "La mayoría de keywords importantes y respaldadas aparece en el perfil generado.",
                "Aumenta consistencia entre perfil, mercado y lectura ATS orientativa.",
                "Conservar estas keywords y evitar agregar términos no respaldados.",
                [keyword.keyword for keyword in matched_keywords[:6]],
                "Quick Wins",
            )
        )
    if missing_keywords:
        risks.append(
            _finding(
                "high" if len(missing_keywords) >= 3 else "medium",
                "Keywords",
                "Keyword importante ausente",
                "Algunas keywords prioritarias y respaldadas no aparecen claramente en el perfil generado.",
                "Puede reducir coincidencia textual con vacantes objetivo.",
                f"Agregar {', '.join(keyword.keyword for keyword in missing_keywords[:3])} en About o experiencia usando evidencia real.",
                [keyword.keyword for keyword in missing_keywords[:5]],
                "Quick Wins",
            )
        )
    unsupported_demanded = [
        keyword.keyword
        for keyword in context.unsupported_market_keywords
        if _priority_value(keyword.priority) in {PriorityLevel.CRITICAL.value, PriorityLevel.HIGH.value}
    ]
    if unsupported_demanded:
        risks.append(
            _finding(
                "medium",
                "ATS",
                "Tecnología muy demandada no respaldada",
                "Hay términos frecuentes o prioritarios del mercado que no están respaldados por la evidencia del candidato.",
                "No deben declararse como experiencia; conviene tratarlos como brecha o plan de desarrollo.",
                f"Mantener {unsupported_demanded[0]} como brecha hasta contar con evidencia verificable.",
                unsupported_demanded[:5],
                "Long Term",
            )
        )
    return _bounded_score(score)


def _audit_requirement_coverage(
    compatibility_report: CompatibilityReport,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    matches = _all_requirement_matches(compatibility_report)
    if not matches:
        return 60.0
    values = [_requirement_score(match) for match in matches]
    score = round(sum(values) / len(values), 1)
    missing_required = [
        match.requirement_name
        for match in matches
        if match.required and _coverage_value(match.coverage) in {RequirementCoverage.MISSING.value, RequirementCoverage.CONFLICT.value}
    ]
    if missing_required:
        risks.append(
            _finding(
                "critical" if len(missing_required) >= 2 else "high",
                "ATS",
                "Requisitos obligatorios sin cobertura",
                "El reporte de compatibilidad detecta requisitos obligatorios faltantes o en conflicto.",
                "Puede limitar la fuerza del perfil para esas vacantes.",
                "No declarar estos requisitos como capacidad; preparar plan de cierre o enfocar postulaciones con mejor alineación.",
                missing_required[:6],
                "Long Term",
            )
        )
    if score >= 80:
        strengths.append(
            _finding(
                "info",
                "Market Alignment",
                "Gran alineación de mercado",
                "La cobertura promedio de requisitos es alta en el reporte de compatibilidad.",
                "Refuerza la calidad del posicionamiento para las vacantes analizadas.",
                "Priorizar vacantes con mayor compatibilidad y adaptar ejemplos con evidencia.",
                [f"Score requisitos: {score:.1f}"],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_ats_skills(
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    if not context.supported_market_keywords:
        return 70.0
    covered = [
        keyword
        for keyword in context.supported_market_keywords
        if _normalize(keyword.keyword) in context.selected_skill_keys or _normalize(keyword.normalized_keyword) in context.selected_skill_keys
    ]
    score = round(len(covered) / len(context.supported_market_keywords) * 100, 1)
    if score < 70:
        missing = [
            keyword.keyword
            for keyword in context.supported_market_keywords
            if keyword not in covered
        ][:5]
        risks.append(
            _finding(
                "medium",
                "Skills",
                "Skills faltantes",
                "No todas las keywords respaldadas del mercado aparecen en skills priorizadas.",
                "Puede debilitar la lectura ATS orientativa.",
                f"Agregar {', '.join(missing[:3])} a skills si sigue estando respaldado por el perfil.",
                missing,
                "Quick Wins",
            )
        )
    else:
        strengths.append(
            _finding(
                "info",
                "Skills",
                "Skills alineadas con ATS",
                "Las skills priorizadas cubren buena parte de las keywords respaldadas del mercado.",
                "Aumenta coherencia entre perfil y vacantes objetivo.",
                "Mantener skills respaldadas y evitar variantes duplicadas.",
                [skill.name for skill in linkedin_profile.prioritized_skills[:5]],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_ats_experience(
    linkedin_profile: LinkedInProfileOutput,
    compatibility_report: CompatibilityReport,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    matches = [
        match
        for match in _all_requirement_matches(compatibility_report)
        if _coverage_value(match.coverage) in {RequirementCoverage.FULL.value, RequirementCoverage.PARTIAL.value}
    ]
    if not matches:
        return 55.0
    reflected = [match for match in matches if _contains(match.requirement_name, context.experience_normalized)]
    score = round(len(reflected) / len(matches) * 100, 1)
    if score < 60:
        risks.append(
            _finding(
                "medium",
                "Experience",
                "Requisitos cubiertos poco visibles en experiencia",
                "Varias capacidades cubiertas en compatibilidad no aparecen en la experiencia reescrita.",
                "Puede reducir señales ATS dentro de la sección más importante del perfil.",
                "Agregar requisitos cubiertos en la experiencia donde exista evidencia directa.",
                [match.requirement_name for match in matches[:5]],
                "Medium Effort",
            )
        )
    else:
        strengths.append(
            _finding(
                "info",
                "Experience",
                "Experiencia alineada con requisitos",
                "La experiencia contiene señales de requisitos cubiertos por compatibilidad.",
                "Refuerza evidencia y trazabilidad para ATS y lectura humana.",
                "Mantener estas referencias ligadas a responsabilidades reales.",
                [match.requirement_name for match in reflected[:5]],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _audit_titles(
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    title_terms = [_normalize(title) for title in market_analysis.suggested_target_titles]
    profile_titles = [linkedin_profile.headline.text, *(entry.suggested_role_title for entry in linkedin_profile.experience)]
    normalized_titles = _normalize(" ".join(profile_titles))
    if any(title and title in normalized_titles for title in title_terms):
        strengths.append(
            _finding(
                "info",
                "ATS",
                "Títulos alineados",
                "El headline o la experiencia usan títulos compatibles con roles objetivo.",
                "Facilita coincidencia con búsquedas por cargo.",
                "Mantener títulos sin inflar seniority.",
                market_analysis.suggested_target_titles[:4],
                "Quick Wins",
            )
        )
        return 92.0
    risks.append(
        _finding(
            "medium",
            "ATS",
            "Títulos objetivo poco visibles",
            "Los títulos sugeridos del mercado no aparecen claramente en headline o experiencia.",
            "Puede reducir coincidencia en búsquedas por cargo.",
            f"Incluir un título objetivo respaldado como {market_analysis.suggested_target_titles[0]} si corresponde a la trayectoria.",
            market_analysis.suggested_target_titles[:4],
            "Quick Wins",
        )
    )
    return 62.0 if context.headline_normalized else 50.0


def _audit_ats_consistency(
    linkedin_profile: LinkedInProfileOutput,
    context: AuditContext,
    findings: list[AuditFinding],
    strengths: list[AuditFinding],
    risks: list[AuditFinding],
) -> float:
    score = 100.0
    unsupported_visible = [
        keyword.keyword
        for keyword in context.unsupported_market_keywords
        if _contains(keyword.keyword, context.headline_normalized)
        or _contains(keyword.keyword, context.about_normalized)
        or _contains(keyword.keyword, context.experience_normalized)
    ]
    if unsupported_visible:
        score -= min(35, len(unsupported_visible) * 15)
        risks.append(
            _finding(
                "high",
                "Consistency",
                "Keyword no respaldada usada como capacidad",
                "Una keyword de mercado sin respaldo aparece en contenido actual del perfil.",
                "Puede crear riesgo de atribuir experiencia no real.",
                "Mover la keyword a notas de revisión o brechas hasta contar con evidencia verificable.",
                unsupported_visible[:5],
                "Quick Wins",
            )
        )
    missing_notes = [
        keyword.keyword
        for keyword in linkedin_profile.ats_keywords
        if not keyword.supported_by_candidate and _evidence_value(keyword.evidence_status) == EvidenceStatus.MISSING.value
    ]
    if missing_notes and not any(_contains(keyword, _normalize(" ".join(linkedin_profile.global_review_notes))) for keyword in missing_notes):
        score -= 8
        findings.append(
            _finding(
                "low",
                "Consistency",
                "Brechas ATS sin nota global",
                "Hay keywords ATS no respaldadas que no aparecen como brecha en notas globales.",
                "Puede hacer menos explícita la separación entre vocabulario de mercado y capacidad real.",
                "Agregar las keywords no respaldadas como brechas en notas de revisión.",
                missing_notes[:5],
                "Quick Wins",
            )
        )
    if score >= 90:
        strengths.append(
            _finding(
                "info",
                "Consistency",
                "Muy buena coherencia",
                "El perfil separa razonablemente capacidades respaldadas y brechas del mercado.",
                "Reduce riesgo de claims no respaldados.",
                "Mantener esta separación al editar manualmente.",
                ["ATS keywords y notas globales"],
                "Quick Wins",
            )
        )
    return _bounded_score(score)


def _build_context(
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    linkedin_profile: LinkedInProfileOutput,
    compatibility_report: CompatibilityReport,
) -> AuditContext:
    visible_text = " ".join(
        [
            linkedin_profile.banner.primary_line,
            linkedin_profile.banner.specialty_line,
            linkedin_profile.banner.supporting_line or "",
            linkedin_profile.headline.text,
            linkedin_profile.about.text,
            *(entry.rewritten_text for entry in linkedin_profile.experience),
        ]
    )
    supported_terms = {
        _normalize(skill.normalized_name or skill.name)
        for skill in candidate_profile.skills
        if _evidence_value(skill.evidence_status) == EvidenceStatus.SUPPORTED.value
    }
    for employment in candidate_profile.employment_history:
        for skill in employment.technologies:
            if _evidence_value(skill.evidence_status) == EvidenceStatus.SUPPORTED.value:
                supported_terms.add(_normalize(skill.normalized_name or skill.name))
    for item in [
        *candidate_profile.leadership_capabilities,
        *candidate_profile.education,
        *candidate_profile.certifications,
        *candidate_profile.languages,
        *(item for employment in candidate_profile.employment_history for item in employment.responsibilities),
    ]:
        if _evidence_value(item.status) == EvidenceStatus.SUPPORTED.value:
            supported_terms.add(_normalize(item.statement))
    candidate_text = _normalize(
        " ".join(
            [
                candidate_profile.professional_identity,
                candidate_profile.summary,
                *(candidate_profile.targetable_roles),
                *(candidate_profile.industries),
                *(skill.name for skill in candidate_profile.skills),
                *(employment.role_title for employment in candidate_profile.employment_history),
                *(employment.employer for employment in candidate_profile.employment_history),
            ]
        )
    )
    sorted_keywords = sorted(
        market_analysis.keywords,
        key=lambda keyword: (
            _priority_rank(keyword.priority),
            -keyword.frequency,
            keyword.normalized_keyword,
        ),
    )
    important = [
        keyword
        for keyword in sorted_keywords
        if _priority_value(keyword.priority) in {PriorityLevel.CRITICAL.value, PriorityLevel.HIGH.value}
    ] or sorted_keywords[:6]
    supported_market = [keyword for keyword in important if _keyword_supported(keyword, supported_terms, candidate_text)]
    unsupported_market = [keyword for keyword in important if not _keyword_supported(keyword, supported_terms, candidate_text)]
    compatibility_strength_terms = {
        _normalize(value)
        for value in [
            *compatibility_report.common_strengths,
            *(strength for job in compatibility_report.job_compatibilities for strength in job.strengths),
        ]
        if value
    }
    return AuditContext(
        visible_text=visible_text,
        visible_text_normalized=_normalize(visible_text),
        headline_normalized=_normalize(linkedin_profile.headline.text),
        about_normalized=_normalize(linkedin_profile.about.text),
        experience_normalized=_normalize(" ".join(entry.rewritten_text for entry in linkedin_profile.experience)),
        banner_normalized=_normalize(
            " ".join(
                [
                    linkedin_profile.banner.primary_line,
                    linkedin_profile.banner.specialty_line,
                    linkedin_profile.banner.supporting_line or "",
                ]
            )
        ),
        supported_terms=supported_terms,
        candidate_terms=set(candidate_text.split()),
        market_keywords=sorted_keywords,
        important_keywords=important,
        supported_market_keywords=supported_market,
        unsupported_market_keywords=unsupported_market,
        selected_skill_keys={_normalize(skill.name) for skill in linkedin_profile.prioritized_skills},
        ats_keyword_keys={_normalize(keyword.keyword) for keyword in linkedin_profile.ats_keywords},
        compatibility_strength_terms={term for term in compatibility_strength_terms if term},
    )


def _keyword_coverage(context: AuditContext) -> tuple[list[MarketKeyword], list[MarketKeyword]]:
    source_keywords = context.supported_market_keywords or context.important_keywords
    matched = [
        keyword
        for keyword in source_keywords
        if _contains(keyword.keyword, context.visible_text_normalized)
        or _contains(keyword.normalized_keyword, context.visible_text_normalized)
        or _normalize(keyword.keyword) in context.ats_keyword_keys
    ]
    missing = [keyword for keyword in source_keywords if keyword not in matched]
    return matched, missing


def _all_requirement_matches(report: CompatibilityReport) -> list[RequirementMatch]:
    return [match for job in report.job_compatibilities for match in job.requirement_matches]


def _requirement_score(match: RequirementMatch) -> float:
    coverage = _coverage_value(match.coverage)
    base = {
        RequirementCoverage.FULL.value: 100.0,
        RequirementCoverage.PARTIAL.value: 65.0,
        RequirementCoverage.INDIRECT.value: 45.0,
        RequirementCoverage.MISSING.value: 0.0,
        RequirementCoverage.CONFLICT.value: 0.0,
        RequirementCoverage.NOT_APPLICABLE.value: 75.0,
    }.get(coverage, 40.0)
    if match.required and coverage in {RequirementCoverage.MISSING.value, RequirementCoverage.CONFLICT.value}:
        return 0.0
    return base


def _recommendations_from_findings(findings: list[AuditFinding]) -> list[AuditRecommendation]:
    actionable = [finding for finding in findings if finding.severity != "info"]
    ordered = sorted(actionable, key=lambda finding: (_priority_order(finding.priority), _severity_order(finding.severity), finding.category))
    recommendations = []
    seen = set()
    for finding in ordered:
        key = (finding.priority, finding.category, finding.recommendation)
        if key in seen:
            continue
        seen.add(key)
        recommendations.append(
            AuditRecommendation(
                priority=finding.priority,
                category=finding.category,
                title=finding.title,
                action=finding.recommendation,
                rationale=finding.impact,
                evidence=finding.evidence,
            )
        )
    return recommendations


def _finding(
    severity: str,
    category: str,
    title: str,
    description: str,
    impact: str,
    recommendation: str,
    evidence: list[str],
    priority: str,
) -> AuditFinding:
    return AuditFinding(
        severity=severity,
        category=category,
        title=title,
        description=description,
        impact=impact,
        recommendation=recommendation,
        evidence=[value for value in evidence if value][:8],
        priority=priority,
    )


def _component(name: str, weight: float, score: float, explanation: str) -> AuditScoreComponent:
    return AuditScoreComponent(name=name, weight=weight, score=_bounded_score(score), explanation=explanation)


def _weighted_component_score(components: list[AuditScoreComponent]) -> float:
    return round(sum(component.score * component.weight for component in components), 1)


def _dedupe_findings(findings: list[AuditFinding]) -> list[AuditFinding]:
    seen = set()
    unique = []
    for finding in findings:
        key = (finding.severity, finding.category, finding.title, finding.description)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _keyword_supported(keyword: MarketKeyword, supported_terms: set[str], candidate_text: str) -> bool:
    keyword_values = {_normalize(keyword.keyword), _normalize(keyword.normalized_keyword)}
    return any(
        _contains(value, candidate_text) or any(_contains(value, term) or _contains(term, value) for term in supported_terms)
        for value in keyword_values
        if value
    )


def _contains(value: str, normalized_text: str) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    if normalized in normalized_text:
        return True
    tokens = [token for token in normalized.split() if len(token) > 2]
    if not tokens:
        return False
    text_tokens = set(normalized_text.split())
    matches = sum(1 for token in tokens if token in text_tokens)
    return matches >= max(1, min(2, len(tokens))) and matches / len(tokens) >= 0.5


def _contains_any(values: list[str], normalized_text: str) -> bool:
    return any(_contains(value, normalized_text) for value in values)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    ascii_text = ascii_text.casefold()
    ascii_text = re.sub(r"[^\w+#./%]+", " ", ascii_text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _split_specialties(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,|;/]+", value) if item.strip()]


def _sentences(value: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"[.!?]\s+", value) if sentence.strip()]


def _keyword_stuffing_terms(normalized_text: str) -> list[str]:
    tokens = [token for token in normalized_text.split() if len(token) > 4]
    counts = Counter(tokens)
    return [token for token, count in counts.items() if count >= 9]


def _has_first_person(value: str) -> bool:
    normalized = _normalize(value)
    return any(marker in f" {normalized} " for marker in (" soy ", " he ", " mi ", " me ", " i ", " my ", " i have "))


def _is_generic_headline(value: str) -> bool:
    normalized = _normalize(value)
    generic = {
        "project manager",
        "program manager",
        "product manager",
        "manager",
        "consultor",
        "consultant",
        "profesional",
        "professional",
    }
    return normalized in generic or len(normalized.split()) <= 2


def _priority_rank(value: object) -> int:
    normalized = _priority_value(value)
    return {
        PriorityLevel.CRITICAL.value: 0,
        PriorityLevel.HIGH.value: 1,
        PriorityLevel.MEDIUM.value: 2,
        PriorityLevel.LOW.value: 3,
    }.get(normalized, 4)


def _priority_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _coverage_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _evidence_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _priority_order(value: str) -> int:
    return {"Quick Wins": 0, "Medium Effort": 1, "Long Term": 2}.get(value, 3)


def _severity_order(value: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(value, 5)


def _stable_json(model: object) -> str:
    if hasattr(model, "model_dump"):
        payload = model.model_dump(mode="json")
    else:
        payload = model
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_validation_findings(findings: list[object]) -> list[str]:
    return [f"{finding.severity}: {finding.path}: {finding.message}" for finding in findings]


def _elapsed_ms(start_time: float) -> int:
    return max(0, int((time.perf_counter() - start_time) * 1000))
