"""Streamlit views for the LinkedIn professional editorial plan."""

from __future__ import annotations

import streamlit as st

from components.editorial_plan_flow import (
    EDITORIAL_PLAN_EXPORT_FAILURE_MESSAGE,
    EDITORIAL_PLAN_EXPORT_SUCCESS_MESSAGE,
    EDITORIAL_PLAN_MISSING_STAGES_MESSAGE,
    EDITORIAL_PLAN_REPROCESS_FAILURE_MESSAGE,
    EDITORIAL_PLAN_SUCCESS_MESSAGE,
    build_editorial_plan_exports_from_session,
    run_editorial_plan_from_session,
)
from exporters.editorial_plan_docx_exporter import EDITORIAL_PLAN_DOCX_FILENAME
from exporters.editorial_plan_html_exporter import EDITORIAL_PLAN_HTML_FILENAME
from exporters.editorial_plan_markdown_exporter import EDITORIAL_PLAN_MARKDOWN_FILENAME
from exporters.editorial_plan_pdf_exporter import EDITORIAL_PLAN_PDF_FILENAME
from exporters.editorial_plan_zip_exporter import EDITORIAL_PLAN_ZIP_FILENAME
from schemas.audit_models import AuditReport
from schemas.compatibility_models import CompatibilityReport
from schemas.editorial_plan_models import (
    EditorialPlanAuditResult,
    EditorialPlanEditValidationResult,
    EditorialPlanGenerationResult,
    LinkedInPostPlan,
    ProfessionalBrandPlan,
)
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.market_models import TargetMarketAnalysis
from services.editorial_plan_edit_validation_service import build_editorial_plan_edit_state
from utils.session import SessionKeys


def render_editorial_plan_tab() -> None:
    """Render professional brand editorial plan generation, editing and downloads."""
    st.markdown("### Marca Profesional")
    profile = _current_profile()
    market = _current_market()
    compatibility = _current_compatibility()
    audit_report = _current_audit_report()
    if profile is None or market is None or compatibility is None or audit_report is None or not audit_report.success:
        st.info(EDITORIAL_PLAN_MISSING_STAGES_MESSAGE)
        return

    plan = _current_plan()
    result = _current_generation_result()
    _render_actions(plan)
    _render_generation_message(result, plan is not None)
    plan = _current_plan()
    if plan is None:
        st.caption("El plan editorial aparecerá aquí cuando la generación se complete correctamente.")
        return

    _render_summary(plan)
    _render_editor(plan)
    validation = _current_edit_validation()
    if validation:
        _render_validation(validation)
    audit = _current_audit()
    if audit:
        _render_audit_details(audit)
    _render_inline_download_buttons()


def render_editorial_plan_downloads_section() -> None:
    """Render editorial plan downloads inside the global downloads tab."""
    st.markdown("#### Plan editorial profesional")
    plan = _current_plan()
    if plan is None:
        st.caption("El plan editorial aparecerá aquí cuando se genere desde la pestaña Marca Profesional.")
        return
    if st.button("Preparar descargas del plan editorial", key="downloads_editorial_plan_export", use_container_width=False):
        export_result = build_editorial_plan_exports_from_session()
        if export_result["success"]:
            st.success(EDITORIAL_PLAN_EXPORT_SUCCESS_MESSAGE)
        else:
            st.error(EDITORIAL_PLAN_EXPORT_FAILURE_MESSAGE)
            for error in export_result["errors"]:
                st.caption(error)

    _render_export_status()
    _render_download_buttons(prefix="downloads_editorial_plan")


def _render_actions(plan: ProfessionalBrandPlan | None) -> None:
    columns = st.columns(2)
    button_label = "Regenerar plan editorial" if plan else "Generar plan editorial"
    with columns[0]:
        if st.button(button_label, key="editorial_plan_generate", use_container_width=True):
            with st.status("Generando plan editorial profesional...", expanded=False) as status:
                result = run_editorial_plan_from_session(
                    force=plan is not None,
                    preserve_previous_on_failure=True,
                    status_callback=lambda label: status.update(label=label, state="running"),
                )
                if result.success:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = EDITORIAL_PLAN_SUCCESS_MESSAGE
                    st.session_state[SessionKeys.PROCESS_ERROR] = None
                    status.update(label="Plan editorial profesional listo.", state="complete")
                else:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                    st.session_state[SessionKeys.PROCESS_ERROR] = EDITORIAL_PLAN_REPROCESS_FAILURE_MESSAGE if plan else result.user_message
                    status.update(label="No fue posible generar el plan editorial.", state="error")
    with columns[1]:
        if st.button(
            "Preparar descargas",
            key="editorial_plan_export",
            disabled=plan is None,
            use_container_width=True,
        ):
            with st.status("Preparando descargas del plan editorial...", expanded=False) as status:
                export_result = build_editorial_plan_exports_from_session()
                if export_result["success"]:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = EDITORIAL_PLAN_EXPORT_SUCCESS_MESSAGE
                    st.session_state[SessionKeys.PROCESS_ERROR] = None
                    status.update(label="Descargas del plan editorial listas.", state="complete")
                else:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                    st.session_state[SessionKeys.PROCESS_ERROR] = EDITORIAL_PLAN_EXPORT_FAILURE_MESSAGE
                    status.update(label="No fue posible preparar las descargas.", state="error")
                    for error in export_result["errors"]:
                        st.error(error)


def _render_generation_message(result: EditorialPlanGenerationResult | None, has_plan: bool) -> None:
    if result is None:
        return
    if result.success:
        st.success(EDITORIAL_PLAN_SUCCESS_MESSAGE)
        if result.reused_from_session:
            st.info("Se reutilizó el plan editorial porque los insumos estructurados no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible generar el plan editorial profesional.")
        if result.error_category:
            st.caption(f"Categoría técnica: {result.error_category}")
        if has_plan:
            st.warning(EDITORIAL_PLAN_REPROCESS_FAILURE_MESSAGE)
    for warning in result.warnings:
        st.warning(warning)


def _render_summary(plan: ProfessionalBrandPlan) -> None:
    posts = plan.calendar.posts
    formats = sorted({str(post.format) for post in posts})
    columns = st.columns(4)
    columns[0].metric("Semanas", len(plan.calendar.weeks))
    columns[1].metric("Publicaciones", len(posts))
    columns[2].metric("Formatos", len(formats))
    columns[3].metric("Idioma", str(plan.output_language))
    st.markdown("#### Resumen")
    st.write(plan.summary)
    st.markdown("#### Calendario")
    rows = [
        {
            "Semana": post.week,
            "Día": _day_label(post.day),
            "Título": post.title,
            "Formato": post.format,
            "Tema": post.theme,
            "Caracteres": post.character_count,
        }
        for post in sorted(posts, key=lambda item: (item.week, _day_order(item.day)))
    ]
    st.table(rows)


def _render_editor(plan: ProfessionalBrandPlan) -> None:
    edit_state = _ensure_edit_state(plan)
    st.markdown("#### Publicaciones")
    week_tabs = st.tabs([f"Semana {index}" for index in range(1, 5)])
    for tab, week in zip(week_tabs, sorted(plan.calendar.weeks, key=lambda item: item.week)):
        with tab:
            for post in sorted(week.posts, key=_day_order):
                _render_post_editor(post, edit_state)
    _sync_edit_state(plan, edit_state)


def _render_post_editor(post: LinkedInPostPlan, edit_state: dict) -> None:
    post_state = _post_state(edit_state, post)
    label = f"{_day_label(post.day)} - {post.title}"
    with st.expander(label, expanded=False):
        st.caption(f"Objetivo: {post.objective} | Tipo: {post.post_type} | Formato: {post.format}")
        st.text_input(
            "Título",
            value=post_state["title"],
            key=_edit_key(post.week, post.day, "title"),
        )
        st.text_input(
            "Tema",
            value=post_state["theme"],
            key=_edit_key(post.week, post.day, "theme"),
        )
        st.text_input(
            "Audiencia",
            value=post_state["audience"],
            key=_edit_key(post.week, post.day, "audience"),
        )
        st.text_area(
            "Hook",
            value=post_state["hook"],
            key=_edit_key(post.week, post.day, "hook"),
            height=80,
        )
        body_key = _edit_key(post.week, post.day, "body")
        st.text_area(
            "Texto",
            value=post_state["body"],
            key=body_key,
            height=260,
        )
        current_body = st.session_state.get(body_key, post_state["body"])
        st.caption(f"Caracteres: {len(str(current_body).strip())}")
        st.text_area(
            "CTA",
            value=post_state["cta"],
            key=_edit_key(post.week, post.day, "cta"),
            height=70,
        )
        st.text_area(
            "Hashtags",
            value="\n".join(post_state["hashtags"]),
            key=_edit_key(post.week, post.day, "hashtags"),
            height=90,
        )
        st.text_area(
            "Keywords utilizadas",
            value="\n".join(post_state["keywords_used"]),
            key=_edit_key(post.week, post.day, "keywords_used"),
            height=90,
        )
        st.text_area(
            "Claims que requieren revisión",
            value="\n".join(post_state["claims_requiring_review"]),
            key=_edit_key(post.week, post.day, "claims_requiring_review"),
            height=90,
        )
        st.text_area(
            "Notas",
            value="\n".join(post_state["notes"]),
            key=_edit_key(post.week, post.day, "notes"),
            height=90,
        )
        if st.button("Copiar texto", key=_edit_key(post.week, post.day, "copy")):
            st.session_state[_copy_key(post.week, post.day)] = _copy_payload(post, post_state)
        if st.session_state.get(_copy_key(post.week, post.day)):
            st.text_area(
                "Texto listo para copiar",
                value=st.session_state[_copy_key(post.week, post.day)],
                key=_edit_key(post.week, post.day, "copy_payload"),
                height=220,
            )


def _render_validation(validation: EditorialPlanEditValidationResult) -> None:
    if validation.passed:
        st.success("Los cambios pasaron la validación local.")
    else:
        st.error("Los cambios no pasaron la validación local.")
    for finding in validation.findings:
        if finding.severity == "error":
            st.caption(f"error: {finding.path}: {finding.message}")
    for warning in validation.warnings:
        st.caption(f"warning: {warning}")


def _render_audit_details(audit: EditorialPlanAuditResult) -> None:
    with st.expander("Auditoría local del plan editorial"):
        st.caption(f"Resultado válido: {'Sí' if audit.passed else 'No'}")
        if audit.character_counts:
            st.caption("Conteo de caracteres:")
            for key, value in audit.character_counts.items():
                st.caption(f"{key}: {value}")
        if audit.findings:
            st.caption("Hallazgos:")
            for finding in audit.findings:
                st.caption(f"{finding.severity}: {finding.path}: {finding.message}")


def _render_inline_download_buttons() -> None:
    st.markdown("#### Descargas")
    _render_export_status()
    _render_download_buttons(prefix="editorial_plan")


def _render_export_status() -> None:
    rows = [
        {"Archivo": EDITORIAL_PLAN_MARKDOWN_FILENAME, "Tamaño": _format_bytes(SessionKeys.EDITORIAL_PLAN_MARKDOWN_BYTES)},
        {"Archivo": EDITORIAL_PLAN_HTML_FILENAME, "Tamaño": _format_bytes(SessionKeys.EDITORIAL_PLAN_HTML_BYTES)},
        {"Archivo": EDITORIAL_PLAN_DOCX_FILENAME, "Tamaño": _format_bytes(SessionKeys.EDITORIAL_PLAN_DOCX_BYTES)},
        {"Archivo": EDITORIAL_PLAN_PDF_FILENAME, "Tamaño": _format_bytes(SessionKeys.EDITORIAL_PLAN_PDF_BYTES)},
        {"Archivo": EDITORIAL_PLAN_ZIP_FILENAME, "Tamaño": _format_bytes(SessionKeys.EDITORIAL_PLAN_ZIP_BYTES)},
    ]
    st.table(rows)


def _render_download_buttons(*, prefix: str) -> None:
    markdown = st.session_state.get(SessionKeys.EDITORIAL_PLAN_MARKDOWN_BYTES)
    html = st.session_state.get(SessionKeys.EDITORIAL_PLAN_HTML_BYTES)
    docx = st.session_state.get(SessionKeys.EDITORIAL_PLAN_DOCX_BYTES)
    pdf = st.session_state.get(SessionKeys.EDITORIAL_PLAN_PDF_BYTES)
    zip_bytes = st.session_state.get(SessionKeys.EDITORIAL_PLAN_ZIP_BYTES)
    if not all([markdown, html, docx, pdf, zip_bytes]):
        st.caption("Prepara las descargas para habilitar los archivos del plan editorial.")
        return
    st.download_button("Plan editorial Markdown", data=markdown, file_name=EDITORIAL_PLAN_MARKDOWN_FILENAME, mime="text/markdown", key=f"{prefix}_md")
    st.download_button("Plan editorial HTML", data=html, file_name=EDITORIAL_PLAN_HTML_FILENAME, mime="text/html", key=f"{prefix}_html")
    st.download_button(
        "Plan editorial DOCX",
        data=docx,
        file_name=EDITORIAL_PLAN_DOCX_FILENAME,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=f"{prefix}_docx",
    )
    st.download_button("Plan editorial PDF", data=pdf, file_name=EDITORIAL_PLAN_PDF_FILENAME, mime="application/pdf", key=f"{prefix}_pdf")
    st.download_button("Plan editorial ZIP", data=zip_bytes, file_name=EDITORIAL_PLAN_ZIP_FILENAME, mime="application/zip", key=f"{prefix}_zip")


def _ensure_edit_state(plan: ProfessionalBrandPlan) -> dict:
    fingerprint = st.session_state.get(SessionKeys.EDITORIAL_PLAN_INPUT_FINGERPRINT)
    edit_state = st.session_state.get(SessionKeys.EDITORIAL_PLAN_EDIT_STATE)
    if not edit_state or edit_state.get("_source_fingerprint") != fingerprint:
        edit_state = build_editorial_plan_edit_state(plan)
        edit_state["_source_fingerprint"] = fingerprint
        st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_STATE] = edit_state
        _reset_edit_widgets()
    return edit_state


def _sync_edit_state(plan: ProfessionalBrandPlan, edit_state: dict) -> None:
    current = {
        "edited": False,
        "_source_fingerprint": edit_state.get("_source_fingerprint"),
        "summary": plan.summary,
        "posts": [],
    }
    for post in sorted(plan.calendar.posts, key=lambda item: (item.week, _day_order(item.day))):
        current["posts"].append(
            {
                "week": post.week,
                "day": post.day,
                "title": st.session_state.get(_edit_key(post.week, post.day, "title"), _post_state(edit_state, post)["title"]),
                "theme": st.session_state.get(_edit_key(post.week, post.day, "theme"), _post_state(edit_state, post)["theme"]),
                "audience": st.session_state.get(_edit_key(post.week, post.day, "audience"), _post_state(edit_state, post)["audience"]),
                "hook": st.session_state.get(_edit_key(post.week, post.day, "hook"), _post_state(edit_state, post)["hook"]),
                "body": st.session_state.get(_edit_key(post.week, post.day, "body"), _post_state(edit_state, post)["body"]),
                "cta": st.session_state.get(_edit_key(post.week, post.day, "cta"), _post_state(edit_state, post)["cta"]),
                "hashtags": _lines(st.session_state.get(_edit_key(post.week, post.day, "hashtags"), "\n".join(_post_state(edit_state, post)["hashtags"]))),
                "keywords_used": _lines(
                    st.session_state.get(
                        _edit_key(post.week, post.day, "keywords_used"),
                        "\n".join(_post_state(edit_state, post)["keywords_used"]),
                    )
                ),
                "claims_requiring_review": _lines(
                    st.session_state.get(
                        _edit_key(post.week, post.day, "claims_requiring_review"),
                        "\n".join(_post_state(edit_state, post)["claims_requiring_review"]),
                    )
                ),
                "notes": _lines(st.session_state.get(_edit_key(post.week, post.day, "notes"), "\n".join(_post_state(edit_state, post)["notes"]))),
            }
        )
    original = build_editorial_plan_edit_state(plan)
    current["edited"] = _state_without_metadata(current) != _state_without_metadata(original)
    previous = st.session_state.get(SessionKeys.EDITORIAL_PLAN_EDIT_STATE)
    if isinstance(previous, dict) and _state_without_metadata(previous) != _state_without_metadata(current):
        _clear_bytes()
    st.session_state[SessionKeys.EDITORIAL_PLAN_EDIT_STATE] = current
    if current["edited"]:
        st.info("Plan editorial editado por el usuario")


def _post_state(edit_state: dict, post: LinkedInPostPlan) -> dict:
    for item in edit_state.get("posts", []):
        if item.get("week") == post.week and str(item.get("day")) == str(post.day):
            return item
    return {
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


def _reset_edit_widgets() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith("editorial_plan_edit_") or str(key).startswith("editorial_plan_copy_"):
            del st.session_state[key]


def _clear_bytes() -> None:
    st.session_state[SessionKeys.EDITORIAL_PLAN_MARKDOWN_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_HTML_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_DOCX_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_PDF_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_ZIP_BYTES] = None
    st.session_state[SessionKeys.EDITORIAL_PLAN_EXPORT_FINGERPRINT] = None


def _copy_payload(post: LinkedInPostPlan, post_state: dict) -> str:
    title = st.session_state.get(_edit_key(post.week, post.day, "title"), post_state["title"])
    hook = st.session_state.get(_edit_key(post.week, post.day, "hook"), post_state["hook"])
    body = st.session_state.get(_edit_key(post.week, post.day, "body"), post_state["body"])
    cta = st.session_state.get(_edit_key(post.week, post.day, "cta"), post_state["cta"])
    hashtags = _lines(st.session_state.get(_edit_key(post.week, post.day, "hashtags"), "\n".join(post_state["hashtags"])))
    return "\n\n".join([str(title).strip(), str(hook).strip(), str(body).strip(), str(cta).strip(), " ".join(hashtags)]).strip()


def _current_profile() -> CandidateProfessionalProfile | None:
    return _model(st.session_state.get(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE), CandidateProfessionalProfile)


def _current_market() -> TargetMarketAnalysis | None:
    return _model(st.session_state.get(SessionKeys.TARGET_MARKET_ANALYSIS), TargetMarketAnalysis)


def _current_compatibility() -> CompatibilityReport | None:
    return _model(st.session_state.get(SessionKeys.COMPATIBILITY_REPORT), CompatibilityReport)


def _current_audit_report() -> AuditReport | None:
    return _model(st.session_state.get(SessionKeys.FINAL_AUDIT_REPORT), AuditReport)


def _current_generation_result() -> EditorialPlanGenerationResult | None:
    return _model(st.session_state.get(SessionKeys.EDITORIAL_PLAN_GENERATION_RESULT), EditorialPlanGenerationResult)


def _current_plan() -> ProfessionalBrandPlan | None:
    return _model(st.session_state.get(SessionKeys.PROFESSIONAL_BRAND_PLAN), ProfessionalBrandPlan)


def _current_audit() -> EditorialPlanAuditResult | None:
    return _model(st.session_state.get(SessionKeys.EDITORIAL_PLAN_AUDIT), EditorialPlanAuditResult)


def _current_edit_validation() -> EditorialPlanEditValidationResult | None:
    return _model(st.session_state.get(SessionKeys.EDITORIAL_PLAN_EDIT_VALIDATION), EditorialPlanEditValidationResult)


def _model(raw, model_class):
    if not raw:
        return None
    try:
        return model_class.model_validate(raw)
    except ValueError:
        return None


def _format_bytes(session_key: str) -> str:
    data = st.session_state.get(session_key) or b""
    return f"{len(data) / 1024:.1f} KB" if data else "Pendiente"


def _edit_key(week: int, day: object, name: str) -> str:
    return f"editorial_plan_edit_{week}_{day}_{name}"


def _copy_key(week: int, day: object) -> str:
    return f"editorial_plan_copy_{week}_{day}"


def _lines(value: object) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _state_without_metadata(state: dict) -> dict:
    return {key: value for key, value in state.items() if key not in {"edited", "_source_fingerprint"}}


def _day_order(value: object) -> int:
    day = getattr(value, "day", value)
    return {"monday": 0, "wednesday": 1, "friday": 2}.get(str(day), 99)


def _day_label(value: object) -> str:
    labels = {
        "monday": "Lunes",
        "wednesday": "Miércoles",
        "friday": "Viernes",
    }
    return labels.get(str(value), str(value))
