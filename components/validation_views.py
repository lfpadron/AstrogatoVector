"""Presentation helpers for validation messages and input summaries."""

from __future__ import annotations

from typing import Any

import streamlit as st

from utils.constants import CV_PREVIEW_CHARS, LANGUAGE_LABELS, LINK_PREVIEW_CHARS
from utils.validators import ValidationMessage


def render_validation_messages(messages: list[ValidationMessage]) -> None:
    """Render validation messages grouped by severity."""
    errors = _messages_by_level(messages, "error")
    warnings = _messages_by_level(messages, "warning")
    infos = _messages_by_level(messages, "info")

    if errors:
        st.error(_format_group("No fue posible validar el formulario", "Errores", errors))

    if warnings:
        st.warning(_format_group("Revisa estas advertencias", "Advertencias", warnings))

    if infos:
        st.info(_format_group("Información", "Notas", infos))


def render_input_summary(validated_input: dict) -> None:
    """Render a compact summary without exposing full captured content."""
    st.markdown("### Resumen de entradas")
    with st.container(border=True):
        cv_source = _cv_source_label(validated_input["cv_source"])
        linkedin_source = _profile_source_label(validated_input["linkedin_source"])
        language = LANGUAGE_LABELS.get(validated_input["output_language"], validated_input["output_language"])

        st.markdown(f"**Fuente principal del CV:** {cv_source}")
        if validated_input.get("cv_filename"):
            st.markdown(f"**Archivo de CV:** {validated_input['cv_filename']}")
        st.markdown(
            f"**Perfil de LinkedIn:** {'sí' if _has_profile(validated_input) else 'no'}"
        )
        st.markdown(f"**Fuente principal del perfil:** {linkedin_source}")
        st.markdown(f"**Idioma seleccionado:** {language}")
        st.markdown(f"**Vacantes capturadas:** {len(validated_input['jobs'])}")

        rows = []
        for job in validated_input["jobs"]:
            company = job.get("company") or "Sin empresa"
            source = "descripción" if job["source"] == "text" else "enlace"
            rows.append(
                {
                    "Vacante": job["index"],
                    "Título": job["title"],
                    "Empresa": company,
                    "Fuente principal": source,
                }
            )
        st.table(rows)


def render_link_diagnostics(
    linkedin_diagnostic: dict[str, Any] | None,
    job_diagnostics: list[dict[str, Any]],
    previews: dict[str, str],
) -> None:
    """Render safe link reading diagnostics and limited previews."""
    st.markdown("### Diagnóstico de enlaces")
    with st.container(border=True):
        if linkedin_diagnostic:
            st.markdown("**Perfil de LinkedIn**")
            st.caption(linkedin_diagnostic.get("message") or "Sin diagnóstico.")
            _render_link_summary(linkedin_diagnostic.get("link_summary"))
            _render_preview(
                "linkedin",
                "Vista previa del contenido recuperado - Perfil de LinkedIn",
                previews,
            )

        if job_diagnostics:
            st.markdown("**Vacantes**")
            rows = []
            for diagnostic in job_diagnostics:
                summary = diagnostic.get("link_summary") or {}
                rows.append(
                    {
                        "Vacante": diagnostic.get("index"),
                        "Título": diagnostic.get("title") or "",
                        "Fuente": "descripción" if diagnostic.get("source") == "text" else "enlace",
                        "Estado": diagnostic.get("message") or "",
                        "Caracteres": summary.get("character_count") if summary else None,
                    }
                )
            st.table(rows)

            for diagnostic in job_diagnostics:
                key = f"job_{diagnostic.get('index')}"
                _render_preview(
                    key,
                    f"Vista previa del contenido recuperado - Vacante {diagnostic.get('index')}",
                    previews,
                )


def _render_link_summary(summary: dict[str, Any] | None) -> None:
    if not summary:
        return

    if summary.get("page_title"):
        st.markdown(f"**Título detectado:** {summary['page_title']}")
    if summary.get("final_url"):
        st.markdown(f"**URL final:** {summary['final_url']}")
    if summary.get("status_code"):
        st.markdown(f"**HTTP:** {summary['status_code']}")
    if summary.get("content_type"):
        st.markdown(f"**Tipo de contenido:** {summary['content_type']}")
    if summary.get("character_count") is not None:
        st.markdown(f"**Caracteres visibles:** {summary['character_count']}")


def _render_preview(key: str, label: str, previews: dict[str, str]) -> None:
    preview = previews.get(key)
    if not preview:
        return

    with st.expander(label):
        st.caption("Vista previa parcial del contenido recuperado desde el enlace.")
        st.text_area(
            label,
            value=preview[:LINK_PREVIEW_CHARS],
            height=220,
            disabled=True,
            label_visibility="collapsed",
        )


def render_cv_diagnostic(summary: dict, preview_text: str | None) -> None:
    """Render safe extraction diagnostics and a limited preview."""
    st.markdown("### Diagnóstico del CV")
    with st.container(border=True):
        st.markdown(f"**Fuente utilizada:** {_cv_source_label(summary['source'])}")
        if summary.get("filename"):
            st.markdown(f"**Archivo:** {summary['filename']}")
        if summary.get("file_type"):
            st.markdown(f"**Tipo:** {summary['file_type'].upper()}")
        if summary.get("page_count") is not None:
            st.markdown(f"**Páginas:** {summary['page_count']}")
        if summary.get("paragraph_count") is not None:
            st.markdown(f"**Párrafos:** {summary['paragraph_count']}")

        st.markdown(f"**Caracteres extraídos:** {summary['character_count']}")
        st.markdown(f"**Palabras aproximadas:** {summary['word_count']}")

        for warning in summary.get("warnings", []):
            st.warning(warning)

        if preview_text:
            preview = preview_text[:CV_PREVIEW_CHARS]
            with st.expander("Vista previa del texto extraído"):
                st.caption(
                    "Vista previa parcial. El contenido completo se conserva únicamente durante la sesión activa."
                )
                st.text_area(
                    "Vista previa parcial del CV",
                    value=preview,
                    height=260,
                    disabled=True,
                    label_visibility="collapsed",
                )


def _messages_by_level(messages: list[ValidationMessage], level: str) -> list[str]:
    return [message.message for message in messages if message.level == level]


def _format_group(title: str, heading: str, messages: list[str]) -> str:
    bullet_lines = "\n".join(f"- {message}" for message in messages)
    return f"**{title}**\n\n**{heading}:**\n{bullet_lines}"


def _profile_source_label(source: str) -> str:
    labels = {
        "text": "texto",
        "url": "enlace",
        "generated": "se generará desde cero",
    }
    return labels.get(source, source)


def _cv_source_label(source: str) -> str:
    labels = {
        "text": "texto",
        "docx": "archivo DOCX",
        "pdf": "archivo PDF",
    }
    return labels.get(source, source)


def _has_profile(validated_input: dict) -> bool:
    return bool(validated_input.get("linkedin_text") or validated_input.get("linkedin_url"))
