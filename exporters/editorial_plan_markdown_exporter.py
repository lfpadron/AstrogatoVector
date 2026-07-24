"""Markdown exporter for LinkedIn professional editorial plans."""

from __future__ import annotations

from schemas.editorial_plan_models import LinkedInPostPlan, ProfessionalBrandPlan
from utils.filename_utils import safe_download_filename

EDITORIAL_PLAN_MARKDOWN_FILENAME = safe_download_filename("linkedin-editorial-plan", "md")


class EditorialPlanMarkdownExporter:
    """Export one professional brand plan to Markdown bytes."""

    def export(self, plan: ProfessionalBrandPlan) -> bytes:
        """Return UTF-8 Markdown bytes for the complete editorial plan."""
        return editorial_plan_markdown(plan).encode("utf-8")


def editorial_plan_markdown(plan: ProfessionalBrandPlan) -> str:
    """Build Markdown text for a professional brand plan."""
    lines = [
        "# Plan editorial profesional de LinkedIn",
        "",
        "## Resumen",
        "",
        plan.summary,
        "",
        "## Objetivos",
        "",
        *_bullets(plan.objectives),
        "",
        "## Fortalezas explotadas",
        "",
        *_bullets(plan.strengths_exploited),
        "",
        "## Temas",
        "",
        *_bullets(plan.themes),
        "",
        "## Riesgos",
        "",
        *_bullets(plan.risks),
        "",
        "## Recomendaciones",
        "",
        *_bullets(plan.recommendations),
        "",
        "## Calendario editorial",
        "",
    ]
    for week in sorted(plan.calendar.weeks, key=lambda item: item.week):
        lines.extend([f"### Semana {week.week}", ""])
        for post in sorted(week.posts, key=_day_order):
            lines.extend(_post_lines(post))
            lines.append("")
    lines.extend(
        [
            "## Nota de uso",
            "",
            "Estos textos son borradores profesionales para revisión humana y publicación manual. "
            "No sustituyen criterio profesional ni garantizan entrevistas, alcance o contratación.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def week_markdown(plan: ProfessionalBrandPlan, week_number: int) -> bytes:
    """Return Markdown bytes for a single week."""
    week = next(week for week in plan.calendar.weeks if week.week == week_number)
    lines = [
        f"# Semana {week.week} - Plan editorial profesional de LinkedIn",
        "",
    ]
    for post in sorted(week.posts, key=_day_order):
        lines.extend(_post_lines(post))
        lines.append("")
    return ("\n".join(lines).strip() + "\n").encode("utf-8")


def post_markdown(post: LinkedInPostPlan) -> bytes:
    """Return Markdown bytes for one post."""
    return ("\n".join(_post_lines(post)).strip() + "\n").encode("utf-8")


def _post_lines(post: LinkedInPostPlan) -> list[str]:
    return [
        f"#### {_day_label(post.day)} - {post.title}",
        "",
        f"- Semana: {post.week}",
        f"- Día: {_day_label(post.day)}",
        f"- Objetivo: {post.objective}",
        f"- Tipo: {post.post_type}",
        f"- Formato: {post.format}",
        f"- Tema: {post.theme}",
        f"- Audiencia: {post.audience}",
        f"- Caracteres: {post.character_count}",
        "",
        "**Hook**",
        "",
        post.hook,
        "",
        "**Texto**",
        "",
        post.body,
        "",
        "**CTA**",
        "",
        post.cta,
        "",
        "**Hashtags**",
        "",
        " ".join(post.hashtags) if post.hashtags else "Sin hashtags",
        "",
        "**Keywords utilizadas**",
        "",
        *_bullets(post.keywords_used),
        "",
        "**Evidencia utilizada**",
        "",
        *_bullets(post.evidence_used),
        "",
        "**Claims que requieren revisión**",
        "",
        *_bullets(post.claims_requiring_review),
        "",
        "**Notas**",
        "",
        *_bullets(post.notes),
    ]


def _bullets(values: list[object]) -> list[str]:
    items = [str(value).strip() for value in values if str(value).strip()]
    return [f"- {item}" for item in items] if items else ["- Sin elementos."]


def _day_order(post: LinkedInPostPlan) -> int:
    return {"monday": 0, "wednesday": 1, "friday": 2}.get(str(post.day), 99)


def _day_label(value: object) -> str:
    labels = {
        "monday": "Lunes",
        "wednesday": "Miércoles",
        "friday": "Viernes",
    }
    return labels.get(str(value), str(value))
