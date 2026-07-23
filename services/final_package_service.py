"""Build the final professional deliverable package from validated results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.deliverable_models import (
    CONTENT_SOURCE_GENERATED_AUDITED,
    CONTENT_SOURCE_USER_EDITED,
    FINAL_PACKAGE_EXPORT_VERSION,
    FINAL_PACKAGE_VERSION,
    FinalDeliverablePackage,
    FinalPackageBuildResult,
)
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_models import (
    ATSKeyword,
    LinkedInProfileOutput,
    PrioritizedSkill,
    RewrittenExperienceEntry,
)
from services.final_package_validation_service import validate_final_package

FINAL_PACKAGE_MISSING_AUDIT_MESSAGE = (
    "Para generar el paquete final es necesario completar primero la auditoría integral."
)
FINAL_PACKAGE_SUCCESS_MESSAGE = "El paquete profesional fue generado y validado correctamente."


class FinalPackageService:
    """Consolidate package content without Streamlit, OpenAI or file output."""

    def build_package(
        self,
        candidate_profile: CandidateProfessionalProfile,
        market_analysis: TargetMarketAnalysis,
        linkedin_profile: LinkedInProfileOutput,
        compatibility_report: CompatibilityReport,
        audit_report: AuditReport,
        output_language: OutputLanguage | str,
        edit_state: dict[str, Any] | None = None,
        banner_available: bool = False,
        banner_fingerprint: str | None = None,
    ) -> FinalPackageBuildResult:
        """Build and validate a final package using audited or explicit edited content."""
        language = _coerce_language(output_language)
        if not audit_report or not audit_report.success:
            return FinalPackageBuildResult(
                success=False,
                validation_passed=False,
                findings=["error: auditoría presente."],
                error_category="missing_final_audit",
                user_message=FINAL_PACKAGE_MISSING_AUDIT_MESSAGE,
            )

        try:
            content = _content_from_edit_state(linkedin_profile, edit_state)
            content_source = CONTENT_SOURCE_USER_EDITED if content["edited"] else CONTENT_SOURCE_GENERATED_AUDITED
            package = FinalDeliverablePackage(
                package_title=_title_for_language(language),
                output_language=language,
                professional_identity=candidate_profile.professional_identity,
                target_roles=_target_roles(candidate_profile, market_analysis),
                headline=content["headline"],
                about=content["about"],
                banner_primary_line=content["banner_primary_line"],
                banner_specialty_line=content["banner_specialty_line"],
                banner_supporting_line=content["banner_supporting_line"],
                experiences=content["experiences"],
                prioritized_skills=content["prioritized_skills"],
                ats_keywords=content["ats_keywords"],
                compatibility_report=compatibility_report,
                audit_report=audit_report,
                executive_summary=_build_executive_summary(
                    candidate_profile,
                    market_analysis,
                    compatibility_report,
                    audit_report,
                    language,
                ),
                key_strengths=_key_strengths(compatibility_report, audit_report),
                critical_gaps=_critical_gaps(compatibility_report, audit_report),
                quick_wins=_quick_wins(audit_report),
                strategic_recommendations=_strategic_recommendations(compatibility_report, audit_report),
                banner_included=banner_available,
                content_source=content_source,
                generated_at=datetime.now().astimezone(),
                package_version=FINAL_PACKAGE_VERSION,
            )
            passed, findings, warnings = validate_final_package(package)
            fingerprint = build_final_package_fingerprint(
                package,
                edit_state=edit_state,
                banner_available=banner_available,
                banner_fingerprint=banner_fingerprint,
            )
            return FinalPackageBuildResult(
                success=passed,
                package=package if passed else None,
                validation_passed=passed,
                findings=findings,
                warnings=warnings,
                package_fingerprint=fingerprint,
                error_category=None if passed else "final_package_validation_failed",
                user_message=None if passed else _validation_message(language),
            )
        except (TypeError, ValueError) as exc:
            return FinalPackageBuildResult(
                success=False,
                validation_passed=False,
                findings=[f"error: {exc}"],
                error_category="final_package_build_failed",
                user_message=_validation_message(language),
            )


def build_final_package_fingerprint(
    package: FinalDeliverablePackage,
    *,
    edit_state: dict[str, Any] | None = None,
    banner_available: bool = False,
    banner_fingerprint: str | None = None,
) -> str:
    """Fingerprint export-relevant content while excluding timestamps."""
    payload = {
        "package_version": package.package_version,
        "export_version": FINAL_PACKAGE_EXPORT_VERSION,
        "output_language": package.output_language,
        "content_source": package.content_source,
        "professional_identity": package.professional_identity,
        "target_roles": package.target_roles,
        "headline": package.headline,
        "about": package.about,
        "banner": {
            "primary": package.banner_primary_line,
            "specialty": package.banner_specialty_line,
            "supporting": package.banner_supporting_line,
            "included": banner_available,
            "fingerprint": banner_fingerprint,
        },
        "experiences": [experience.model_dump(mode="json") for experience in package.experiences],
        "skills": [skill.model_dump(mode="json") for skill in package.prioritized_skills],
        "keywords": [keyword.model_dump(mode="json") for keyword in package.ats_keywords],
        "compatibility": package.compatibility_report.model_dump(mode="json"),
        "audit": package.audit_report.model_dump(mode="json"),
        "edit_state": _safe_edit_state(edit_state),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _content_from_edit_state(
    linkedin_profile: LinkedInProfileOutput,
    edit_state: dict[str, Any] | None,
) -> dict[str, Any]:
    if not edit_state:
        return {
            "edited": False,
            "headline": linkedin_profile.headline.text,
            "about": linkedin_profile.about.text,
            "banner_primary_line": linkedin_profile.banner.primary_line,
            "banner_specialty_line": linkedin_profile.banner.specialty_line,
            "banner_supporting_line": linkedin_profile.banner.supporting_line,
            "experiences": [item.model_copy(deep=True) for item in linkedin_profile.experience],
            "prioritized_skills": [item.model_copy(deep=True) for item in linkedin_profile.prioritized_skills],
            "ats_keywords": [item.model_copy(deep=True) for item in linkedin_profile.ats_keywords],
        }

    experiences = []
    source_experiences = list(linkedin_profile.experience)
    edited_experiences = list(edit_state.get("experience") or [])
    for index, original in enumerate(source_experiences):
        edited = edited_experiences[index] if index < len(edited_experiences) and isinstance(edited_experiences[index], dict) else {}
        experiences.append(
            RewrittenExperienceEntry(
                source_role_title=original.source_role_title,
                suggested_role_title=str(edited.get("suggested_role_title") or original.suggested_role_title),
                employer=original.employer,
                rewritten_text=str(edited.get("rewritten_text") or original.rewritten_text),
                included_keywords=original.included_keywords,
                unsupported_claims=original.unsupported_claims,
            )
        )

    selected_skills = _selected_names(edit_state.get("selected_skills"))
    selected_keywords = _selected_names(edit_state.get("selected_keywords"))
    skills = _filter_by_name(linkedin_profile.prioritized_skills, selected_skills, "name")
    keywords = _filter_by_name(linkedin_profile.ats_keywords, selected_keywords, "keyword")
    banner = edit_state.get("banner") if isinstance(edit_state.get("banner"), dict) else {}
    content = {
        "edited": bool(edit_state.get("edited")),
        "headline": str(edit_state.get("headline") or linkedin_profile.headline.text),
        "about": str(edit_state.get("about") or linkedin_profile.about.text),
        "banner_primary_line": str(banner.get("primary_line") or linkedin_profile.banner.primary_line),
        "banner_specialty_line": str(banner.get("specialty_line") or linkedin_profile.banner.specialty_line),
        "banner_supporting_line": str(banner.get("supporting_line") or linkedin_profile.banner.supporting_line or "") or None,
        "experiences": experiences,
        "prioritized_skills": skills,
        "ats_keywords": keywords,
    }
    original = _content_from_edit_state(linkedin_profile, None)
    comparable = {key: value for key, value in content.items() if key != "edited"}
    original_comparable = {key: value for key, value in original.items() if key != "edited"}
    content["edited"] = bool(edit_state.get("edited")) or _dump_for_compare(comparable) != _dump_for_compare(original_comparable)
    return content


def _build_executive_summary(
    profile: CandidateProfessionalProfile,
    market: TargetMarketAnalysis,
    compatibility: CompatibilityReport,
    audit: AuditReport,
    language: OutputLanguage,
) -> str:
    best_job = _best_job(compatibility)
    strengths = _join_short(_key_strengths(compatibility, audit), limit=3)
    gaps = _join_short(_critical_gaps(compatibility, audit), limit=3)
    quick_wins = _join_short(_quick_wins(audit), limit=2)
    if language == OutputLanguage.EN:
        parts = [
            f"The profile is positioned primarily for {market.target_role_family}.",
            _score_sentence_en(audit),
            f"The strongest demonstrable alignment is Job {best_job.job_index}, with {best_job.compatibility_score:.1f}/100." if best_job else "",
            f"Main strengths: {strengths}." if strengths else "",
            f"Priority gaps: {gaps}." if gaps else "",
            f"Quick wins: {quick_wins}." if quick_wins else "",
        ]
    else:
        parts = [
            f"El perfil se posiciona principalmente para funciones de {market.target_role_family}.",
            _score_sentence_es(audit),
            f"La mayor alineación demostrable corresponde a la Vacante {best_job.job_index}, con {best_job.compatibility_score:.1f}/100." if best_job else "",
            f"Las fortalezas principales se concentran en {strengths}." if strengths else "",
            f"Las brechas prioritarias están relacionadas con {gaps}." if gaps else "",
            f"Quick Wins recomendados: {quick_wins}." if quick_wins else "",
        ]
    if profile.professional_identity and not parts[0].casefold().startswith(profile.professional_identity.casefold()):
        pass
    return " ".join(part for part in parts if part)


def _score_sentence_es(audit: AuditReport) -> str:
    parts = []
    if audit.linkedin_positioning:
        parts.append(f"La auditoría de LinkedIn obtuvo {audit.linkedin_positioning.score:.1f}/100")
    if audit.ats_estimation:
        parts.append(f"la lectura ATS {audit.ats_estimation.score:.1f}/100")
    if not parts:
        return ""
    return " y ".join(parts) + "."


def _score_sentence_en(audit: AuditReport) -> str:
    parts = []
    if audit.linkedin_positioning:
        parts.append(f"the LinkedIn audit scored {audit.linkedin_positioning.score:.1f}/100")
    if audit.ats_estimation:
        parts.append(f"the ATS reading scored {audit.ats_estimation.score:.1f}/100")
    if not parts:
        return ""
    return "The package shows " + " and ".join(parts) + "."


def _key_strengths(compatibility: CompatibilityReport, audit: AuditReport) -> list[str]:
    values = [*compatibility.common_strengths]
    values.extend(finding.title for finding in audit.strengths)
    for job in compatibility.job_compatibilities:
        values.extend(job.strengths[:2])
    return _dedupe(values)[:8]


def _critical_gaps(compatibility: CompatibilityReport, audit: AuditReport) -> list[str]:
    values = [*compatibility.common_gaps]
    values.extend(finding.title for finding in audit.risks if finding.severity in {"high", "critical", "medium"})
    for job in compatibility.job_compatibilities:
        values.extend(job.critical_gaps[:2])
    return _dedupe(values)[:8]


def _quick_wins(audit: AuditReport) -> list[str]:
    return _dedupe([recommendation.action for recommendation in audit.quick_wins])[:8]


def _strategic_recommendations(compatibility: CompatibilityReport, audit: AuditReport) -> list[str]:
    values = [*compatibility.strategic_recommendations]
    values.extend(recommendation.action for recommendation in audit.recommendations)
    return _dedupe(values)[:10]


def _target_roles(profile: CandidateProfessionalProfile, market: TargetMarketAnalysis) -> list[str]:
    return _dedupe([*profile.targetable_roles, *market.suggested_target_titles])[:12]


def _best_job(compatibility: CompatibilityReport):
    if not compatibility.job_compatibilities:
        return None
    target_index = compatibility.highest_compatibility_job_index
    for job in compatibility.job_compatibilities:
        if job.job_index == target_index:
            return job
    return max(compatibility.job_compatibilities, key=lambda item: item.compatibility_score)


def _filter_by_name(items: list[Any], selected_names: list[str], field_name: str) -> list[Any]:
    if not selected_names:
        return []
    selected = {name.casefold() for name in selected_names}
    return [item.model_copy(deep=True) for item in items if str(getattr(item, field_name)).casefold() in selected]


def _selected_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _join_short(values: list[str], *, limit: int) -> str:
    return ", ".join(values[:limit])


def _coerce_language(value: OutputLanguage | str) -> OutputLanguage:
    return value if isinstance(value, OutputLanguage) else OutputLanguage(str(value))


def _title_for_language(language: OutputLanguage) -> str:
    return "Professional Positioning Package" if language == OutputLanguage.EN else "Paquete profesional de posicionamiento"


def _validation_message(language: OutputLanguage) -> str:
    if language == OutputLanguage.EN:
        return "The package could not be generated because validation found blocking issues."
    return "No fue posible generar el paquete porque la validación encontró hallazgos bloqueantes."


def _safe_edit_state(edit_state: dict[str, Any] | None) -> Any:
    if edit_state is None:
        return None
    try:
        json.dumps(edit_state, ensure_ascii=False, sort_keys=True, default=str)
        return edit_state
    except TypeError:
        return str(edit_state)


def _dump_for_compare(value: Any) -> str:
    def default(item: Any) -> Any:
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        return str(item)

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=default)
