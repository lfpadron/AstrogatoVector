"""Markdown exporter for targeted CVs."""

from __future__ import annotations

from schemas.targeted_cv_models import TargetedCV
from utils.filename_utils import safe_download_filename

TARGETED_CV_MARKDOWN_FILENAME_TEMPLATE = "astrogato-vector-cv-vacante-{index:02d}.md"


class TargetedCVMarkdownExporter:
    """Export one targeted CV to Markdown bytes."""

    def export(self, targeted_cv: TargetedCV) -> bytes:
        return targeted_cv_to_markdown(targeted_cv).encode("utf-8")


def targeted_cv_to_markdown(targeted_cv: TargetedCV) -> str:
    """Render a targeted CV without internal scores, findings or evidence notes."""
    header = targeted_cv.header
    lines = [
        f"# {header.candidate_name or header.professional_title}",
        "",
        f"**{header.professional_title}**",
        "",
        _contact_line(targeted_cv),
        "",
        "## Perfil profesional",
        "",
        targeted_cv.summary.text,
        "",
        "## Competencias clave",
        "",
        *_bullets(skill.name for skill in sorted(targeted_cv.skills, key=lambda item: item.priority)),
        "",
        "## Experiencia profesional",
        "",
    ]
    for entry in targeted_cv.experience:
        if not entry.included:
            continue
        date_line = _date_line(entry.start_date, entry.end_date)
        location = f" | {entry.location}" if entry.location else ""
        lines.extend(
            [
                f"### {entry.display_role_title} | {entry.employer}",
                "",
                f"{date_line}{location}".strip(),
                "",
                *_bullets(bullet.text for bullet in entry.bullets),
                "",
            ]
        )
    _append_optional_section(lines, "Educación", [entry.text for entry in targeted_cv.education if entry.visible])
    _append_optional_section(
        lines,
        "Certificaciones",
        [entry.text for entry in targeted_cv.certifications if entry.visible],
    )
    _append_optional_section(lines, "Idiomas", [entry.text for entry in targeted_cv.languages if entry.visible])
    return "\n".join(lines).strip() + "\n"


def targeted_cv_download_filename(targeted_cv: TargetedCV, extension: str) -> str:
    """Return a safe individual download filename for a targeted CV."""
    title = targeted_cv.target_job_title or f"vacante-{targeted_cv.target_job_index:02d}"
    return safe_download_filename(f"astrogato-vector-cv-vacante-{targeted_cv.target_job_index:02d}-{title}", extension)


def _append_optional_section(lines: list[str], title: str, values: list[str]) -> None:
    if not values:
        return
    lines.extend([f"## {title}", "", *_bullets(values), ""])


def _contact_line(targeted_cv: TargetedCV) -> str:
    header = targeted_cv.header
    values = [header.location, header.email, header.phone, header.linkedin_url]
    return " | ".join(value for value in values if value) or ""


def _date_line(start_date: str | None, end_date: str | None) -> str:
    if start_date and end_date:
        return f"{start_date} - {end_date}"
    if start_date:
        return f"{start_date} - Actual"
    return end_date or ""


def _bullets(values) -> list[str]:
    return [f"- {value}" for value in values if str(value).strip()]
