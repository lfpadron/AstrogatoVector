"""HTML exporter for LinkedIn professional editorial plans."""

from __future__ import annotations

import html

from schemas.editorial_plan_models import LinkedInPostPlan, ProfessionalBrandPlan
from utils.filename_utils import safe_download_filename

EDITORIAL_PLAN_HTML_FILENAME = safe_download_filename("linkedin-editorial-plan", "html")


class EditorialPlanHTMLExporter:
    """Export one professional brand plan to a standalone HTML document."""

    def export(self, plan: ProfessionalBrandPlan) -> bytes:
        """Return standalone UTF-8 HTML bytes."""
        return editorial_plan_html(plan).encode("utf-8")


def editorial_plan_html(plan: ProfessionalBrandPlan) -> str:
    """Build a safe standalone HTML document."""
    posts_html = []
    for week in sorted(plan.calendar.weeks, key=lambda item: item.week):
        posts_html.append(f"<section><h2>Semana {week.week}</h2>")
        for post in sorted(week.posts, key=_day_order):
            posts_html.append(_post_html(post))
        posts_html.append("</section>")
    return f"""<!doctype html>
<html lang="{_language(plan.output_language)}">
<head>
  <meta charset="utf-8">
  <title>Plan editorial profesional de LinkedIn</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #1f2937; line-height: 1.48; margin: 36px; }}
    h1 {{ font-size: 28px; margin-bottom: 6px; }}
    h2 {{ border-top: 1px solid #d1d5db; padding-top: 18px; margin-top: 28px; }}
    h3 {{ margin-bottom: 4px; }}
    .meta {{ color: #4b5563; font-size: 13px; margin-bottom: 14px; }}
    .post {{ border: 1px solid #d1d5db; border-radius: 6px; padding: 16px; margin: 14px 0; }}
    .label {{ font-weight: 700; margin-top: 10px; }}
    ul {{ margin-top: 4px; }}
    .tags {{ color: #0f766e; }}
  </style>
</head>
<body>
  <h1>Plan editorial profesional de LinkedIn</h1>
  <p class="meta">Borrador profesional para revisión humana y publicación manual.</p>
  <h2>Resumen</h2>
  <p>{_escape(plan.summary)}</p>
  {_list_section("Objetivos", [str(item) for item in plan.objectives])}
  {_list_section("Fortalezas explotadas", plan.strengths_exploited)}
  {_list_section("Temas", plan.themes)}
  {_list_section("Riesgos", plan.risks)}
  {_list_section("Recomendaciones", plan.recommendations)}
  <h2>Calendario editorial</h2>
  {''.join(posts_html)}
  <h2>Nota de uso</h2>
  <p>Estos textos son orientativos. Revisa evidencia, tono y confidencialidad antes de publicarlos.</p>
</body>
</html>
"""


def _post_html(post: LinkedInPostPlan) -> str:
    return f"""
<article class="post">
  <h3>{_escape(_day_label(post.day))} - {_escape(post.title)}</h3>
  <p class="meta">Semana {post.week} | Objetivo: {_escape(str(post.objective))} | Tipo: {_escape(str(post.post_type))} | Formato: {_escape(str(post.format))} | Caracteres: {post.character_count}</p>
  <p><strong>Tema:</strong> {_escape(post.theme)}</p>
  <p><strong>Audiencia:</strong> {_escape(post.audience)}</p>
  <p class="label">Hook</p>
  <p>{_escape(post.hook)}</p>
  <p class="label">Texto</p>
  {_paragraphs(post.body)}
  <p class="label">CTA</p>
  <p>{_escape(post.cta)}</p>
  <p class="label">Hashtags</p>
  <p class="tags">{_escape(" ".join(post.hashtags) if post.hashtags else "Sin hashtags")}</p>
  {_list_section("Keywords utilizadas", post.keywords_used, heading_level=4)}
  {_list_section("Evidencia utilizada", post.evidence_used, heading_level=4)}
  {_list_section("Claims que requieren revisión", post.claims_requiring_review, heading_level=4)}
  {_list_section("Notas", post.notes, heading_level=4)}
</article>
"""


def _list_section(title: str, values: list[str], *, heading_level: int = 2) -> str:
    tag = f"h{heading_level}"
    items = [str(value).strip() for value in values if str(value).strip()]
    if not items:
        items = ["Sin elementos."]
    lis = "".join(f"<li>{_escape(item)}</li>" for item in items)
    return f"<{tag}>{_escape(title)}</{tag}><ul>{lis}</ul>"


def _paragraphs(value: str) -> str:
    blocks = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    return "".join(f"<p>{_escape(block)}</p>" for block in blocks)


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _day_order(post: LinkedInPostPlan) -> int:
    return {"monday": 0, "wednesday": 1, "friday": 2}.get(str(post.day), 99)


def _day_label(value: object) -> str:
    labels = {
        "monday": "Lunes",
        "wednesday": "Miércoles",
        "friday": "Viernes",
    }
    return labels.get(str(value), str(value))


def _language(value: object) -> str:
    return str(getattr(value, "value", value)) or "es"
