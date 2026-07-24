"""Build, apply and validate editable editorial plan state locally."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.editorial_plan_models import (
    EditorialCalendar,
    EditorialCalendarWeek,
    EditorialPlanEditValidationResult,
    LinkedInPostPlan,
    ProfessionalBrandPlan,
)
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from services.editorial_plan_audit_service import audit_editorial_plan


def build_editorial_plan_edit_state(plan: ProfessionalBrandPlan) -> dict[str, Any]:
    """Create Streamlit-friendly editable state for a professional brand plan."""
    return {
        "edited": False,
        "summary": plan.summary,
        "posts": [
            {
                "week": post.week,
                "day": post.day,
                "title": post.title,
                "theme": post.theme,
                "audience": post.audience,
                "hook": post.hook,
                "body": post.body,
                "cta": post.cta,
                "hashtags": list(post.hashtags),
                "keywords_used": list(post.keywords_used),
                "claims_requiring_review": list(post.claims_requiring_review),
                "notes": list(post.notes),
            }
            for post in plan.calendar.posts
        ],
    }


def apply_editorial_plan_edit_state(
    plan: ProfessionalBrandPlan,
    edit_state: dict[str, Any] | None,
) -> ProfessionalBrandPlan:
    """Apply explicit user edits while preserving plan metadata and structure."""
    if not edit_state:
        return plan
    updates = edit_state.get("posts") if isinstance(edit_state.get("posts"), list) else []
    posts: list[LinkedInPostPlan] = []
    for index, post in enumerate(plan.calendar.posts):
        update = updates[index] if index < len(updates) and isinstance(updates[index], dict) else {}
        body = _text(update.get("body"), post.body)
        posts.append(
            post.model_copy(
                update={
                    "title": _text(update.get("title"), post.title),
                    "theme": _text(update.get("theme"), post.theme),
                    "audience": _text(update.get("audience"), post.audience),
                    "hook": _text(update.get("hook"), post.hook),
                    "body": body,
                    "cta": _text(update.get("cta"), post.cta),
                    "hashtags": _string_list(update.get("hashtags"), post.hashtags)[:5],
                    "keywords_used": _string_list(update.get("keywords_used"), post.keywords_used),
                    "claims_requiring_review": _string_list(
                        update.get("claims_requiring_review"),
                        post.claims_requiring_review,
                    ),
                    "notes": _string_list(update.get("notes"), post.notes),
                    "character_count": len(body.strip()),
                }
            )
        )
    weeks = []
    for week_number in range(1, 5):
        week_posts = [post for post in posts if post.week == week_number]
        weeks.append(EditorialCalendarWeek(week=week_number, posts=week_posts))
    return plan.model_copy(
        update={
            "summary": _text(edit_state.get("summary"), plan.summary),
            "calendar": EditorialCalendar(weeks=weeks),
        }
    )


def validate_editorial_plan_edits(
    plan: ProfessionalBrandPlan,
    candidate_profile: CandidateProfessionalProfile,
    market_analysis: TargetMarketAnalysis,
    compatibility_report: CompatibilityReport,
    audit_report: AuditReport,
    edit_state: dict[str, Any] | None,
) -> EditorialPlanEditValidationResult:
    """Validate edited editorial plan content without calling external services."""
    edited = apply_editorial_plan_edit_state(plan, edit_state)
    audit = audit_editorial_plan(edited, candidate_profile, market_analysis, compatibility_report, audit_report)
    warnings = [f"{finding.path}: {finding.message}" for finding in audit.findings if finding.severity == "warning"]
    return EditorialPlanEditValidationResult(
        passed=audit.passed,
        findings=audit.findings,
        warnings=warnings,
    )


def editorial_plan_edit_state_changed(plan: ProfessionalBrandPlan, edit_state: dict[str, Any] | None) -> bool:
    """Return whether editable state differs from the original plan."""
    if not edit_state:
        return False
    edited = deepcopy(edit_state)
    edited.pop("edited", None)
    edited.pop("_source_fingerprint", None)
    original = build_editorial_plan_edit_state(plan)
    original.pop("edited", None)
    return edited != original


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _string_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, str):
        values = [line.strip() for line in value.splitlines() if line.strip()]
        return values or fallback
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        return values or fallback
    return fallback
