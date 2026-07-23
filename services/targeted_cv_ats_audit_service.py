"""Local ATS-oriented scoring for targeted CVs."""

from __future__ import annotations

import re

from schemas.compatibility_models import JobCompatibility
from schemas.enums import EvidenceStatus, RequirementCoverage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import JobAnalysis
from schemas.targeted_cv_models import TARGETED_CV_ATS_WEIGHTS, TargetedCV, TargetedCVATSAudit
from services.targeted_cv_audit_service import audit_targeted_cv


def audit_targeted_cv_ats(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
) -> TargetedCVATSAudit:
    """Score ATS alignment using only structured local inputs."""
    local_audit = audit_targeted_cv(targeted_cv, candidate_profile, job_analysis, job_compatibility)
    supported_keywords = _supported_job_keywords(candidate_profile, job_analysis, job_compatibility)
    used_keywords = _unique([keyword for keyword in targeted_cv.ats_keywords_used if _norm(keyword)])
    supported_norm = {_norm(keyword) for keyword in supported_keywords}
    used_norm = {_norm(keyword) for keyword in used_keywords}
    unsupported = [keyword for keyword in used_keywords if _norm(keyword) not in supported_norm]
    missing_supported = [keyword for keyword in supported_keywords if _norm(keyword) not in used_norm]

    component_scores = {
        "keyword_coverage": _keyword_coverage_score(supported_keywords, used_keywords),
        "requirement_coverage": _requirement_coverage_score(job_compatibility),
        "skills_coverage": _skills_coverage_score(targeted_cv, candidate_profile, job_compatibility),
        "title_alignment": _title_alignment_score(targeted_cv, job_analysis),
        "readability": _readability_score(targeted_cv),
        "consistency": _consistency_score(local_audit.findings, unsupported, targeted_cv),
    }
    overall = round(
        sum(component_scores[name] * weight for name, weight in TARGETED_CV_ATS_WEIGHTS.items()),
        1,
    )
    findings = [
        f"{finding.severity}: {finding.path}: {finding.message}"
        for finding in local_audit.findings
        if finding.severity == "error"
    ]
    warnings = [
        f"{finding.severity}: {finding.path}: {finding.message}"
        for finding in local_audit.findings
        if finding.severity == "warning"
    ]
    if unsupported:
        findings.append("El CV contiene keywords usadas que no están respaldadas por evidencia.")
    if missing_supported:
        warnings.append("Existen keywords relevantes y respaldadas que no aparecen en el CV objetivo.")
    return TargetedCVATSAudit(
        job_index=targeted_cv.target_job_index,
        overall_score=overall,
        component_scores=component_scores,
        weights=dict(TARGETED_CV_ATS_WEIGHTS),
        supported_keywords=supported_keywords,
        keywords_used=used_keywords,
        missing_supported_keywords=missing_supported,
        unsupported_keywords_removed=unsupported,
        findings=_unique(findings),
        warnings=_unique(warnings),
    )


def _supported_job_keywords(
    candidate_profile: CandidateProfessionalProfile,
    job_analysis: JobAnalysis,
    job_compatibility: JobCompatibility,
) -> list[str]:
    job_terms: list[str] = []
    job_terms.extend(job_analysis.exact_keywords)
    job_terms.extend(job_analysis.technical_skills)
    job_terms.extend(job_analysis.soft_skills)
    job_terms.extend(job_analysis.leadership_skills)
    job_terms.extend(job_analysis.tools_and_technologies)
    for requirement in job_analysis.requirements:
        job_terms.append(requirement.name)
        job_terms.extend(requirement.exact_keywords)

    supported_terms = {
        _norm(skill.name)
        for skill in candidate_profile.skills
        if str(skill.evidence_status) == EvidenceStatus.SUPPORTED.value
    }
    supported_terms.update(
        _norm(skill.normalized_name)
        for skill in candidate_profile.skills
        if str(skill.evidence_status) == EvidenceStatus.SUPPORTED.value
    )
    for match in job_compatibility.requirement_matches:
        if str(match.evidence_status) == EvidenceStatus.SUPPORTED.value and _coverage_is_usable(match.coverage):
            supported_terms.add(_norm(match.requirement_name))
            supported_terms.add(_norm(match.normalized_requirement))
            supported_terms.update(_norm(value) for value in match.matched_candidate_items)

    supported: list[str] = []
    for term in job_terms:
        normalized = _norm(term)
        if normalized and any(normalized == value or normalized in value or value in normalized for value in supported_terms):
            supported.append(term)
    return _unique(supported)


def _keyword_coverage_score(supported_keywords: list[str], used_keywords: list[str]) -> float:
    if not supported_keywords:
        return 100.0
    supported = {_norm(keyword) for keyword in supported_keywords}
    used = {_norm(keyword) for keyword in used_keywords}
    return round(100 * len(supported & used) / len(supported), 1)


def _requirement_coverage_score(job_compatibility: JobCompatibility) -> float:
    if not job_compatibility.requirement_matches:
        return 100.0
    total = 0.0
    for match in job_compatibility.requirement_matches:
        coverage = str(match.coverage)
        points = {
            RequirementCoverage.FULL.value: 100.0,
            RequirementCoverage.PARTIAL.value: 70.0,
            RequirementCoverage.INDIRECT.value: 45.0,
            RequirementCoverage.MISSING.value: 0.0,
            RequirementCoverage.CONFLICT.value: 0.0,
            RequirementCoverage.NOT_APPLICABLE.value: 100.0,
        }.get(coverage, 0.0)
        if str(match.evidence_status) != EvidenceStatus.SUPPORTED.value:
            points *= 0.55 if str(match.evidence_status) == EvidenceStatus.INFERRED.value else 0
        total += points
    return round(total / len(job_compatibility.requirement_matches), 1)


def _skills_coverage_score(
    targeted_cv: TargetedCV,
    candidate_profile: CandidateProfessionalProfile,
    job_compatibility: JobCompatibility,
) -> float:
    supported = {
        _norm(skill.name)
        for skill in candidate_profile.skills
        if str(skill.evidence_status) == EvidenceStatus.SUPPORTED.value
    }
    needed = {
        _norm(match.requirement_name)
        for match in job_compatibility.requirement_matches
        if str(match.evidence_status) == EvidenceStatus.SUPPORTED.value and _coverage_is_usable(match.coverage)
    }
    if not needed:
        return 100.0
    selected = {_norm(skill.name) for skill in targeted_cv.skills}
    covered = {name for name in needed if name in selected or name in supported}
    return round(100 * len(covered) / len(needed), 1)


def _title_alignment_score(targeted_cv: TargetedCV, job_analysis: JobAnalysis) -> float:
    job_tokens = _tokens(job_analysis.title)
    title_tokens = _tokens(targeted_cv.header.professional_title + " " + targeted_cv.header.target_role_title)
    if not job_tokens:
        return 100.0
    overlap = len(job_tokens & title_tokens) / len(job_tokens)
    score = 55 + 45 * overlap
    return round(min(100.0, score), 1)


def _readability_score(targeted_cv: TargetedCV) -> float:
    score = 100.0
    summary_len = len(targeted_cv.summary.text)
    if summary_len < 220 or summary_len > 900:
        score -= 15
    included_entries = [entry for entry in targeted_cv.experience if entry.included]
    for entry in included_entries:
        if not 1 <= len(entry.bullets) <= 6:
            score -= 10
        for bullet in entry.bullets:
            if len(bullet.text) > 320:
                score -= 5
            if len(_tokens(bullet.text)) < 8:
                score -= 3
    if len(targeted_cv.skills) > 18:
        score -= 12
    return round(max(0.0, min(100.0, score)), 1)


def _consistency_score(findings: list[object], unsupported_keywords: list[str], targeted_cv: TargetedCV) -> float:
    errors = sum(1 for finding in findings if getattr(finding, "severity", "") == "error")
    warnings = sum(1 for finding in findings if getattr(finding, "severity", "") == "warning")
    duplicate_keywords = len(targeted_cv.ats_keywords_used) - len({_norm(value) for value in targeted_cv.ats_keywords_used})
    score = 100 - errors * 18 - warnings * 4 - len(unsupported_keywords) * 12 - duplicate_keywords * 5
    return round(max(0.0, min(100.0, score)), 1)


def _coverage_is_usable(value: object) -> bool:
    return str(getattr(value, "value", value)) in {
        RequirementCoverage.FULL.value,
        RequirementCoverage.PARTIAL.value,
        RequirementCoverage.INDIRECT.value,
    }


def _tokens(text: str) -> set[str]:
    stop = {"de", "la", "el", "en", "y", "for", "of", "the", "to", "with"}
    return {token for token in re.findall(r"[a-z0-9]+", _norm(text)) if token not in stop and len(token) > 1}


def _norm(value: object) -> str:
    text = str(value or "").casefold().strip()
    return re.sub(r"\s+", " ", text)


def _unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        normalized = _norm(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(value)
    return output
