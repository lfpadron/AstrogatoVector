"""Presentation of generated and pending Astrogato Vector results."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import streamlit as st

from components.candidate_extraction_flow import (
    REPROCESS_FAILURE_MESSAGE,
    run_candidate_extraction_from_session,
)
from components.compatibility_flow import (
    COMPATIBILITY_MISSING_STAGES_MESSAGE,
    COMPATIBILITY_REPROCESS_FAILURE_MESSAGE,
    run_compatibility_from_session,
)
from components.final_audit_flow import FINAL_AUDIT_REPROCESS_FAILURE_MESSAGE, run_final_audit_from_session
from components.final_package_flow import (
    FINAL_PACKAGE_REUSE_MESSAGE,
    build_final_package_from_session,
)
from components.application_communication_view import (
    render_application_communication_downloads_section,
    render_application_communication_tab,
)
from components.job_analysis_flow import JOB_REPROCESS_FAILURE_MESSAGE, run_job_analysis_from_session
from components.linkedin_profile_flow import (
    LINKEDIN_PROFILE_MISSING_STAGES_MESSAGE,
    LINKEDIN_PROFILE_REPROCESS_FAILURE_MESSAGE,
    build_linkedin_profile_edit_state,
    run_linkedin_profile_generation_from_session,
)
from components.targeted_cv_flow import (
    TARGETED_CV_EXPORT_FAILURE_MESSAGE,
    TARGETED_CV_EXPORT_SUCCESS_MESSAGE,
    TARGETED_CV_MISSING_STAGES_MESSAGE,
    TARGETED_CV_REPROCESS_FAILURE_MESSAGE,
    TARGETED_CV_SUCCESS_MESSAGE,
    build_targeted_cv_exports_from_session,
    run_all_targeted_cv_generation_from_session,
    run_targeted_cv_generation_from_session,
)
from schemas.evidence_models import (
    Achievement,
    CandidateProfessionalProfile,
    CandidateSkill,
    EmploymentEntry,
    EvidenceItem,
    EvidenceReference,
)
from schemas.audit_models import AuditFinding, AuditRecommendation, AuditReport, AuditScoreComponent
from schemas.deliverable_models import FinalPackageBuildResult
from schemas.compatibility_analysis_models import CompatibilityAnalysisResult
from schemas.compatibility_models import (
    COMPATIBILITY_BAND_LABELS_ES,
    COMPATIBILITY_DIMENSION_WEIGHTS,
    COMPATIBILITY_METHODOLOGY_VERSION,
    CompatibilityReport,
    JobCompatibility,
    RequirementMatch,
)
from schemas.enums import RequirementCoverage
from schemas.extraction_models import CandidateExtractionResult
from schemas.banner_models import DEFAULT_BANNER_FILENAME, BannerRenderInput, BannerRenderResult
from schemas.input_models import CandidateInput
from schemas.job_analysis_models import JobAnalysisResult
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis
from schemas.profile_generation_models import LinkedInProfileGenerationResult
from schemas.profile_models import ATSKeyword, LinkedInProfileOutput, PrioritizedSkill, RewrittenExperienceEntry
from schemas.targeted_cv_models import (
    TargetedCV,
    TargetedCVATSAudit,
    TargetedCVAuditResult,
    TargetedCVEditableValidationResult,
    TargetedCVGenerationResult,
)
from exporters.final_package_exporter import (
    FINAL_ZIP_FILENAME,
    INDIVIDUAL_DOCX_FILENAME,
    INDIVIDUAL_HTML_FILENAME,
    INDIVIDUAL_MARKDOWN_FILENAME,
    INDIVIDUAL_PDF_FILENAME,
)
from exporters.targeted_cv_markdown_exporter import targeted_cv_download_filename
from exporters.targeted_cv_zip_exporter import TARGETED_CV_ZIP_FILENAME
from services.banner_audit_service import audit_banner_result
from services.banner_service import (
    BANNER_TEMPLATE_LABELS,
    BannerService,
    build_banner_render_fingerprint,
)
from services.final_audit_service import FINAL_AUDIT_MISSING_STAGES_MESSAGE, FINAL_AUDIT_SUCCESS_MESSAGE
from services.targeted_cv_edit_validation_service import build_targeted_cv_edit_state
from utils.constants import DEFAULT_OUTPUT_LANGUAGE, EMPTY_RESULT_MESSAGE, RESULT_TABS
from utils.session import SessionKeys, clear_final_package_state

STATUS_LABELS = {
    "SUPPORTED": "Respaldado",
    "INFERRED": "Inferido",
    "MISSING": "Faltante",
    "CONFLICT": "Conflicto",
}


def render_results() -> None:
    """Render the candidate extraction result and placeholders for later stages."""
    st.markdown("## Resultados")
    tabs = st.tabs(RESULT_TABS)
    with tabs[0]:
        _render_candidate_profile_tab()
    with tabs[1]:
        _render_market_analysis_tab()
    with tabs[2]:
        _render_compatibility_tab()
    with tabs[3]:
        _render_final_audit_tab()
    with tabs[4]:
        _render_targeted_cv_tab()
    with tabs[5]:
        render_application_communication_tab()
    with tabs[8]:
        _render_downloads_tab()

    for tab in tabs[6:8]:
        with tab:
            st.info(EMPTY_RESULT_MESSAGE)


def _render_final_audit_tab() -> None:
    st.markdown("### Auditoría integral LinkedIn y ATS")
    profile = _current_profile()
    market = _current_market_analysis()
    output = _current_linkedin_profile_output()
    compatibility = _current_compatibility_report()
    result = _current_final_audit_report()

    _render_final_audit_reprocess_button(profile, market, output, compatibility)

    if result is None:
        if profile is None or market is None or output is None or compatibility is None:
            st.info(FINAL_AUDIT_MISSING_STAGES_MESSAGE)
        else:
            st.info("La auditoría aparecerá aquí cuando el análisis final se complete correctamente.")
        return

    _render_final_audit_message(result)
    if not result.success or result.linkedin_positioning is None or result.ats_estimation is None:
        _render_final_audit_details(result)
        return

    _render_final_audit_dashboard(result)
    st.markdown("#### Resumen ejecutivo")
    st.write(result.executive_summary or "No disponible.")

    st.markdown("#### Desglose de scores")
    linkedin_col, ats_col = st.columns(2)
    with linkedin_col:
        _render_audit_component_table("LinkedIn", result.linkedin_positioning.components)
    with ats_col:
        _render_audit_component_table("ATS", result.ats_estimation.components)

    st.markdown("#### Hallazgos")
    _render_audit_findings_table(result.findings)
    st.markdown("#### Fortalezas")
    _render_audit_findings_table(result.strengths, empty_message="No se detectaron fortalezas destacadas.")
    st.markdown("#### Riesgos")
    _render_audit_findings_table(result.risks, empty_message="No se detectaron riesgos prioritarios.")
    st.markdown("#### Quick Wins")
    _render_audit_recommendations(result.quick_wins, empty_message="No hay Quick Wins pendientes.")
    st.markdown("#### Recomendaciones")
    _render_audit_recommendations(result.recommendations, empty_message="No hay recomendaciones pendientes.")
    _render_final_audit_details(result)


def _render_final_audit_reprocess_button(
    profile: CandidateProfessionalProfile | None,
    market: TargetMarketAnalysis | None,
    output: LinkedInProfileOutput | None,
    compatibility: CompatibilityReport | None,
) -> None:
    if profile is None or market is None or output is None or compatibility is None:
        return
    if st.button("Reauditar", use_container_width=False):
        with st.status("Reauditando posicionamiento...", expanded=False) as status:
            result = run_final_audit_from_session(
                force=True,
                preserve_previous_on_failure=True,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if result.success:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = FINAL_AUDIT_SUCCESS_MESSAGE
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Auditoría integral actualizada.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = FINAL_AUDIT_REPROCESS_FAILURE_MESSAGE
                status.update(label="La reauditoría falló.", state="error")


def _render_final_audit_message(result: AuditReport) -> None:
    if result.success:
        st.success(FINAL_AUDIT_SUCCESS_MESSAGE)
        if result.reused_from_session:
            st.info("Se reutilizó la auditoría integral porque los resultados estructurados no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible calcular la auditoría integral de posicionamiento.")
        if result.error_category:
            st.caption(f"Categoría técnica: {result.error_category}")
    for warning in result.warnings:
        st.warning(warning)


def _render_final_audit_dashboard(result: AuditReport) -> None:
    linkedin_score = result.linkedin_positioning.score if result.linkedin_positioning else 0
    ats_score = result.ats_estimation.score if result.ats_estimation else 0
    compatibility_score = result.average_compatibility_score or 0
    columns = st.columns(3)
    _render_score_kpi(columns[0], "LinkedIn", linkedin_score)
    _render_score_kpi(columns[1], "ATS", ats_score)
    _render_score_kpi(columns[2], "Compatibilidad promedio", compatibility_score)


def _render_score_kpi(column, label: str, score: float) -> None:
    with column:
        st.metric(label, f"{score:.0f}")
        st.progress(min(100, max(0, int(round(score)))))


def _render_audit_component_table(title: str, components: list[AuditScoreComponent]) -> None:
    st.markdown(f"**{title}**")
    st.table(
        [
            {
                "Componente": component.name,
                "Peso": f"{component.weight:.0%}",
                "Score": f"{component.score:.1f}",
                "Explicación": component.explanation,
            }
            for component in components
        ]
    )


def _render_audit_findings_table(
    findings: list[AuditFinding],
    *,
    empty_message: str = "No hay hallazgos para mostrar.",
) -> None:
    if not findings:
        st.caption(empty_message)
        return
    st.table(
        [
            {
                "Severidad": finding.severity,
                "Categoría": finding.category,
                "Hallazgo": finding.title,
                "Impacto": finding.impact,
                "Prioridad": finding.priority,
                "Recomendación": finding.recommendation,
                "Evidencia": "; ".join(finding.evidence),
            }
            for finding in findings
        ]
    )


def _render_audit_recommendations(
    recommendations: list[AuditRecommendation],
    *,
    empty_message: str,
) -> None:
    if not recommendations:
        st.caption(empty_message)
        return
    for priority in ("Quick Wins", "Medium Effort", "Long Term"):
        group = [recommendation for recommendation in recommendations if recommendation.priority == priority]
        if not group:
            continue
        st.markdown(f"**{priority}**")
        for recommendation in group:
            with st.container(border=True):
                st.markdown(f"**{recommendation.title}**")
                st.caption(recommendation.category)
                st.write(recommendation.action)
                st.caption(recommendation.rationale)
                if recommendation.evidence:
                    st.caption("Evidencia: " + "; ".join(recommendation.evidence))


def _render_final_audit_details(result: AuditReport | None) -> None:
    if result is None:
        return
    with st.expander("Detalles de auditoría"):
        st.caption(f"Resultado válido: {'Sí' if result.success else 'No'}")
        st.caption(f"Latencia: {_token_label(result.latency_ms)} ms")
        st.caption(f"Versión de prompt: {result.prompt_version or 'No disponible'}")
        st.caption(f"Versión de metodología: {result.methodology_version or 'No disponible'}")
        st.caption(f"Fingerprint reutilizado: {'Sí' if result.reused_from_session else 'No'}")
        st.caption(f"Categoría de error: {result.error_category or 'No disponible'}")
        if result.audit_findings:
            st.caption("Hallazgos de validación local:")
            for finding in result.audit_findings:
                st.caption(finding)


def _render_candidate_profile_tab() -> None:
    st.markdown("### Perfil de LinkedIn optimizado")
    _render_linkedin_profile_generation_section()
    st.divider()
    st.markdown("### Perfil profesional extraído")
    _render_reprocess_button()

    result = _current_extraction_result()
    profile = _current_profile()

    if result is None and profile is None:
        st.info(EMPTY_RESULT_MESSAGE)
        return

    if result is not None:
        _render_result_message(result, has_profile=profile is not None)

    if profile is None:
        _render_technical_details(result)
        return

    _render_identity(profile)
    _render_industries(profile)
    _render_employment_history(profile.employment_history)
    _render_skills(profile.skills)
    _render_evidence_group("Liderazgo", profile.leadership_capabilities)
    _render_evidence_group("Educación", profile.education)
    _render_evidence_group("Certificaciones", profile.certifications)
    _render_evidence_group("Idiomas", profile.languages)
    _render_human_review(profile, result)
    _render_technical_details(result)


def _render_linkedin_profile_generation_section() -> None:
    profile = _current_profile()
    market = _current_market_analysis()
    result = _current_linkedin_generation_result()
    output = _current_linkedin_profile_output()

    _render_linkedin_reprocess_button(profile, market)

    if result is not None:
        _render_linkedin_generation_message(result, has_output=output is not None)

    if output is None:
        if profile is None or market is None:
            st.info(LINKEDIN_PROFILE_MISSING_STAGES_MESSAGE)
        else:
            st.info("El perfil optimizado aparecerá aquí cuando la generación se complete correctamente.")
        _render_linkedin_generation_details(result)
        return

    edit_state = _ensure_linkedin_edit_state(output)
    st.caption("Selecciona el contenido para copiarlo. Los cambios editables no modifican el objeto auditado.")
    _render_banner_editor(output, edit_state)
    _render_headline_editor(output, edit_state)
    _render_about_editor(output, edit_state)
    _render_rewritten_experience_editor(output.experience, edit_state)
    _render_prioritized_skills(output.prioritized_skills, edit_state)
    _render_ats_keywords(output.ats_keywords, edit_state)
    _render_profile_review_notes(output, result)
    _sync_linkedin_edit_state(output, edit_state)
    _render_linkedin_generation_details(result)


def _render_linkedin_reprocess_button(
    profile: CandidateProfessionalProfile | None,
    market: TargetMarketAnalysis | None,
) -> None:
    if profile is None or market is None:
        return
    if st.button("Reprocesar perfil de LinkedIn", use_container_width=False):
        with st.status("Reprocesando perfil de LinkedIn...", expanded=False) as status:
            result = run_linkedin_profile_generation_from_session(
                force=True,
                preserve_previous_on_failure=True,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if result.success:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = "El perfil de LinkedIn fue reprocesado y validado correctamente."
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Perfil de LinkedIn reprocesado.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = LINKEDIN_PROFILE_REPROCESS_FAILURE_MESSAGE
                status.update(label="El reprocesamiento del perfil de LinkedIn falló.", state="error")


def _render_linkedin_generation_message(
    result: LinkedInProfileGenerationResult,
    *,
    has_output: bool,
) -> None:
    if result.success:
        st.success(
            "El perfil de LinkedIn fue generado y validado correctamente.\n\n"
            "Revisa y adapta los textos antes de publicarlos. Astrogato Vector optimiza la presentación "
            "de la evidencia disponible, pero no sustituye la revisión profesional del usuario."
        )
        if result.reused_from_session:
            st.info("Se reutilizó el perfil generado durante esta sesión porque la evidencia y las vacantes no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible generar el perfil optimizado de LinkedIn.")
        if result.error_category:
            st.caption(f"Categoría técnica: {result.error_category}")
        if has_output:
            st.warning(LINKEDIN_PROFILE_REPROCESS_FAILURE_MESSAGE)

    for warning in result.warnings:
        st.warning(warning)


def _render_banner_editor(output: LinkedInProfileOutput, edit_state: dict) -> None:
    st.markdown("#### Banner profesional")
    banner = edit_state["banner"]
    st.text_area("Línea principal", value=banner["primary_line"], key=_edit_key("banner_primary"), height=70)
    st.text_area("Especialidades", value=banner["specialty_line"], key=_edit_key("banner_specialty"), height=70)
    st.text_area("Línea de apoyo", value=banner["supporting_line"], key=_edit_key("banner_supporting"), height=70)
    st.text_area("Concepto visual", value=banner["visual_concept"], key=_edit_key("banner_visual"), height=90)
    template_ids = list(BANNER_TEMPLATE_LABELS)
    recommended_template = banner["recommended_template"]
    selected_template = recommended_template if recommended_template in template_ids else "professional_light"
    template_key = _edit_key("banner_template")
    if st.session_state.get(template_key, selected_template) not in template_ids:
        st.session_state[template_key] = selected_template
    st.selectbox(
        "Estilo visual",
        options=template_ids,
        index=template_ids.index(selected_template),
        format_func=lambda template_id: BANNER_TEMPLATE_LABELS[template_id],
        key=template_key,
    )
    _render_banner_png_controls(edit_state)
    _render_text_list("Keywords del banner auditado", [*output.headline.included_keywords, *output.about.included_keywords])


def _render_banner_png_controls(edit_state: dict) -> None:
    payload = _current_banner_render_payload(edit_state)
    current_fingerprint = _current_banner_fingerprint(payload)
    stored_result = _current_banner_render_result()
    stored_bytes = st.session_state.get(SessionKeys.BANNER_IMAGE_BYTES)
    has_current_banner = bool(
        stored_result
        and stored_result.success
        and stored_bytes
        and current_fingerprint
        and stored_result.fingerprint == current_fingerprint
    )
    has_previous_banner = bool(stored_result and stored_result.success and stored_bytes)
    button_label = "Regenerar banner PNG" if has_previous_banner else "Generar banner PNG"

    if st.button(button_label, key="generate_linkedin_banner_png", use_container_width=False):
        if has_current_banner:
            st.info("Se reutilizó el banner PNG vigente porque el contenido editable no cambió.")
        else:
            result = BannerService().render_banner(payload)
            if result.success:
                audit = audit_banner_result(result)
                if not audit.passed:
                    result = result.model_copy(
                        update={
                            "success": False,
                            "image_bytes": None,
                            "errors": [*result.errors, *audit.findings],
                            "contrast_passed": audit.contrast_valid,
                            "safe_zone_passed": audit.safe_zone_valid,
                            "overflow_passed": audit.overflow_valid,
                        }
                    )
            _store_banner_render_result(result)
            stored_result = _current_banner_render_result()
            stored_bytes = st.session_state.get(SessionKeys.BANNER_IMAGE_BYTES)
            current_fingerprint = result.fingerprint
            has_current_banner = bool(stored_result and stored_result.success and stored_bytes)
            has_previous_banner = bool(stored_result and stored_result.success and stored_bytes)

    if has_previous_banner and not has_current_banner:
        st.warning("El contenido del banner cambio. Regenera el PNG para actualizar la vista previa y descarga.")
        return

    if stored_result is None:
        return

    if stored_result.success and stored_bytes:
        st.image(stored_bytes, caption="Vista previa del banner PNG", use_container_width=True)
        _render_banner_validation(stored_result)
        if _banner_is_downloadable(stored_result):
            st.download_button(
                label="Descargar banner PNG",
                data=stored_bytes,
                file_name=stored_result.filename or DEFAULT_BANNER_FILENAME,
                mime="image/png",
            )
        return

    _render_banner_validation(stored_result)


def _current_banner_render_payload(edit_state: dict) -> dict:
    banner = edit_state["banner"]
    return {
        "primary_line": st.session_state.get(_edit_key("banner_primary"), banner["primary_line"]),
        "specialty_line": st.session_state.get(_edit_key("banner_specialty"), banner["specialty_line"]),
        "supporting_line": st.session_state.get(_edit_key("banner_supporting"), banner["supporting_line"]),
        "visual_concept": st.session_state.get(_edit_key("banner_visual"), banner["visual_concept"]),
        "template_id": st.session_state.get(_edit_key("banner_template"), banner["recommended_template"]),
        "output_language": _current_output_language(),
    }


def _current_banner_fingerprint(payload: dict) -> str | None:
    try:
        return build_banner_render_fingerprint(BannerRenderInput.model_validate(payload))
    except ValueError:
        return None


def _store_banner_render_result(result: BannerRenderResult) -> None:
    st.session_state[SessionKeys.BANNER_RENDER_RESULT] = result.model_dump()
    st.session_state[SessionKeys.BANNER_IMAGE_BYTES] = result.image_bytes if result.success else None
    st.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] = result.fingerprint if result.success else None
    st.session_state[SessionKeys.BANNER_LAST_RENDER] = datetime.now().isoformat(timespec="seconds")
    clear_final_package_state()


def _current_banner_render_result() -> BannerRenderResult | None:
    raw = st.session_state.get(SessionKeys.BANNER_RENDER_RESULT)
    if not raw:
        return None
    try:
        return BannerRenderResult.model_validate(raw)
    except ValueError:
        return None


def _render_banner_validation(result: BannerRenderResult) -> None:
    st.markdown("**Validación del banner**")
    st.markdown(f"{_check_label(result.width == 1584 and result.height == 396)} Dimensiones: {result.width} × {result.height}")
    st.markdown(f"{_check_label(result.contrast_passed)} Contraste")
    st.markdown(f"{_check_label(result.safe_zone_passed)} Zona segura")
    st.markdown(f"{_check_label(result.overflow_passed)} Texto dentro del lienzo")
    st.caption(f"Plantilla: {BANNER_TEMPLATE_LABELS.get(result.template_id or '', result.template_id or 'No disponible')}")
    st.caption(
        "Tamaños de fuente: "
        f"principal {result.primary_font_size or 'N/D'}, "
        f"especialidades {result.specialty_font_size or 'N/D'}, "
        f"apoyo {result.supporting_font_size or 'N/D'}"
    )
    st.caption(
        "Líneas: "
        f"principal {result.primary_line_count}, "
        f"especialidades {result.specialty_line_count}, "
        f"apoyo {result.supporting_line_count}"
    )
    for warning in result.warnings:
        st.warning(warning)
    for error in result.errors:
        st.error(error)
    with st.expander("Detalles técnicos del banner"):
        st.caption(f"Formato: {result.format}")
        st.caption(f"Archivo: {result.filename or DEFAULT_BANNER_FILENAME}")
        st.caption(f"Renderer: {result.renderer_version}")
        st.caption(f"Fingerprint: {result.fingerprint or 'No disponible'}")
        st.caption(f"Último render: {st.session_state.get(SessionKeys.BANNER_LAST_RENDER) or 'No disponible'}")


def _check_label(passed: bool) -> str:
    return "✓" if passed else "✗"


def _banner_is_downloadable(result: BannerRenderResult) -> bool:
    return result.success and result.contrast_passed and result.safe_zone_passed and result.overflow_passed


def _render_headline_editor(output: LinkedInProfileOutput, edit_state: dict) -> None:
    st.markdown("#### Headline")
    st.text_area("Headline editable", value=edit_state["headline"], key=_edit_key("headline"), height=90)
    current = st.session_state.get(_edit_key("headline"), edit_state["headline"])
    st.caption(f"{len(current)} de 220 caracteres")
    if len(current) > 220:
        st.warning("El headline editado supera 220 caracteres.")
    _render_text_list("Keywords incluidas", output.headline.included_keywords)


def _render_about_editor(output: LinkedInProfileOutput, edit_state: dict) -> None:
    st.markdown("#### About")
    st.text_area("About editable", value=edit_state["about"], key=_edit_key("about"), height=260)
    current = st.session_state.get(_edit_key("about"), edit_state["about"])
    st.caption(f"{len(current)} caracteres")
    _render_text_list("Keywords incluidas", output.about.included_keywords)
    _render_text_list("Claims que requieren revisión", output.about.claims_requiring_review)


def _render_rewritten_experience_editor(
    experiences: list[RewrittenExperienceEntry],
    edit_state: dict,
) -> None:
    st.markdown("#### Experiencia reescrita")
    for index, experience in enumerate(experiences):
        label = f"{experience.employer} — {experience.source_role_title}"
        with st.expander(label):
            st.caption(f"Cargo fuente: {experience.source_role_title}")
            st.text_input(
                "Cargo sugerido",
                value=edit_state["experience"][index]["suggested_role_title"],
                key=_edit_key(f"experience_title_{index}"),
            )
            st.text_area(
                "Texto reescrito",
                value=edit_state["experience"][index]["rewritten_text"],
                key=_edit_key(f"experience_text_{index}"),
                height=180,
            )
            _render_text_list("Keywords", experience.included_keywords)
            if experience.unsupported_claims:
                st.error("Esta experiencia contiene claims no respaldados y no deberia presentarse como valida.")
                _render_text_list("Claims no respaldados", experience.unsupported_claims)


def _render_prioritized_skills(skills: list[PrioritizedSkill], edit_state: dict) -> None:
    st.markdown("#### Skills priorizadas")
    top_skills = sorted(skills, key=lambda skill: skill.priority_rank)[:5]
    _render_text_list("Top 5 recomendadas", [skill.name for skill in top_skills])
    skill_names = [skill.name for skill in skills]
    st.multiselect(
        "Skills seleccionadas",
        options=skill_names,
        default=[name for name in edit_state["selected_skills"] if name in skill_names],
        key=_edit_key("selected_skills"),
    )
    if skills:
        st.table(
            [
                {
                    "Prioridad": skill.priority_rank,
                    "Skill": skill.name,
                    "Categoría": skill.category,
                    "Evidencia": skill.evidence_status,
                    "Razón": skill.rationale,
                    "Ubicación": ", ".join(skill.recommended_placement),
                }
                for skill in sorted(skills, key=lambda item: item.priority_rank)
            ]
        )


def _render_ats_keywords(keywords: list[ATSKeyword], edit_state: dict) -> None:
    st.markdown("#### Keywords ATS")
    st.warning("Las palabras clave no respaldadas no deben agregarse al perfil como si representaran experiencia real.")
    keyword_names = [keyword.keyword for keyword in keywords]
    st.multiselect(
        "Keywords seleccionadas",
        options=keyword_names,
        default=[keyword for keyword in edit_state["selected_keywords"] if keyword in keyword_names],
        key=_edit_key("selected_keywords"),
    )
    if keywords:
        st.table(
            [
                {
                    "Keyword": keyword.keyword,
                    "Prioridad": keyword.priority,
                    "Frecuencia": keyword.frequency_in_jobs,
                    "Respaldada": "Sí" if keyword.supported_by_candidate else "No",
                    "Estado": keyword.evidence_status,
                    "Secciones": ", ".join(keyword.recommended_sections),
                }
                for keyword in keywords
            ]
        )


def _render_profile_review_notes(
    output: LinkedInProfileOutput,
    result: LinkedInProfileGenerationResult | None,
) -> None:
    st.markdown("#### Revisión humana necesaria")
    with st.container(border=True):
        _render_text_list("Notas globales", output.global_review_notes)
        warnings = [finding for finding in (result.audit_findings if result else []) if finding.startswith("warning:")]
        _render_text_list("Advertencias de auditoría", warnings)


def _render_linkedin_generation_details(result: LinkedInProfileGenerationResult | None) -> None:
    if result is None:
        return
    with st.expander("Detalles de generación"):
        st.caption(f"Resultado válido: {'Sí' if result.success else 'No'}")
        st.caption(f"Modelo: {result.model_used or 'No disponible'}")
        st.caption(f"Tokens de entrada: {_token_label(result.input_tokens)}")
        st.caption(f"Tokens de salida: {_token_label(result.output_tokens)}")
        st.caption(f"Tokens totales: {_token_label(result.total_tokens)}")
        st.caption(f"Latencia: {_token_label(result.latency_ms)} ms")
        st.caption(f"Request ID: {result.request_id or 'No disponible'}")
        st.caption(f"Versión de prompt: {result.prompt_version or 'No disponible'}")
        st.caption(f"Categoría de error: {result.error_category or 'No disponible'}")
        st.caption(f"Reintentable: {'Sí' if result.retryable else 'No'}")
        st.caption(f"Reutilizado en sesión: {'Sí' if result.reused_from_session else 'No'}")
        if result.warnings:
            st.caption("Warnings:")
            for warning in result.warnings:
                st.caption(warning)
        if result.audit_findings:
            st.caption("Hallazgos de auditoría:")
            for finding in result.audit_findings:
                st.caption(finding)


def _ensure_linkedin_edit_state(output: LinkedInProfileOutput) -> dict:
    fingerprint = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_GENERATION_FINGERPRINT)
    edit_state = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_EDIT_STATE)
    if not edit_state or edit_state.get("_source_fingerprint") != fingerprint:
        edit_state = build_linkedin_profile_edit_state(output)
        edit_state["_source_fingerprint"] = fingerprint
        st.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] = edit_state
        _reset_linkedin_edit_widgets(edit_state)
    return edit_state


def _reset_linkedin_edit_widgets(edit_state: dict) -> None:
    keys = [
        "banner_primary",
        "banner_specialty",
        "banner_supporting",
        "banner_visual",
        "banner_template",
        "headline",
        "about",
        "selected_skills",
        "selected_keywords",
    ]
    keys.extend(f"experience_title_{index}" for index, _ in enumerate(edit_state["experience"]))
    keys.extend(f"experience_text_{index}" for index, _ in enumerate(edit_state["experience"]))
    for key in keys:
        widget_key = _edit_key(key)
        if widget_key in st.session_state:
            del st.session_state[widget_key]


def _sync_linkedin_edit_state(output: LinkedInProfileOutput, edit_state: dict) -> None:
    current = {
        "edited": False,
        "_source_fingerprint": edit_state.get("_source_fingerprint"),
        "banner": {
            "primary_line": st.session_state.get(_edit_key("banner_primary"), edit_state["banner"]["primary_line"]),
            "specialty_line": st.session_state.get(_edit_key("banner_specialty"), edit_state["banner"]["specialty_line"]),
            "supporting_line": st.session_state.get(_edit_key("banner_supporting"), edit_state["banner"]["supporting_line"]),
            "visual_concept": st.session_state.get(_edit_key("banner_visual"), edit_state["banner"]["visual_concept"]),
            "recommended_template": st.session_state.get(_edit_key("banner_template"), edit_state["banner"]["recommended_template"]),
        },
        "headline": st.session_state.get(_edit_key("headline"), edit_state["headline"]),
        "about": st.session_state.get(_edit_key("about"), edit_state["about"]),
        "experience": [],
        "selected_skills": st.session_state.get(_edit_key("selected_skills"), edit_state["selected_skills"]),
        "selected_keywords": st.session_state.get(_edit_key("selected_keywords"), edit_state["selected_keywords"]),
    }
    for index, experience in enumerate(edit_state["experience"]):
        current["experience"].append(
            {
                "employer": experience["employer"],
                "source_role_title": experience["source_role_title"],
                "suggested_role_title": st.session_state.get(
                    _edit_key(f"experience_title_{index}"),
                    experience["suggested_role_title"],
                ),
                "rewritten_text": st.session_state.get(
                    _edit_key(f"experience_text_{index}"),
                    experience["rewritten_text"],
                ),
                "included_keywords": experience["included_keywords"],
            }
        )
    original = build_linkedin_profile_edit_state(output)
    current["edited"] = _edit_state_without_metadata(current) != _edit_state_without_metadata(original)
    previous = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_EDIT_STATE)
    if isinstance(previous, dict) and _edit_state_without_metadata(previous) != _edit_state_without_metadata(current):
        clear_final_package_state()
    st.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] = current
    if current["edited"]:
        st.info("Contenido editado por el usuario")


def _edit_state_without_metadata(state: dict) -> dict:
    return {key: value for key, value in state.items() if key not in {"edited", "_source_fingerprint"}}


def _edit_key(name: str) -> str:
    return f"linkedin_profile_edit_{name}"


def _render_reprocess_button() -> None:
    if not st.session_state.get(SessionKeys.VALIDATED_INPUT):
        return
    if st.button("Reprocesar perfil", use_container_width=False):
        with st.status("Reprocesando perfil...", expanded=False) as status:
            result = run_candidate_extraction_from_session(
                force=True,
                preserve_previous_on_failure=True,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if result.success:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = (
                    "El perfil profesional fue reprocesado y validado correctamente."
                )
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Perfil profesional reprocesado.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = REPROCESS_FAILURE_MESSAGE
                status.update(label="El reprocesamiento falló.", state="error")


def _render_market_analysis_tab() -> None:
    st.markdown("### Mercado objetivo")
    st.warning(
        "Este análisis describe patrones y requisitos presentes en las vacantes seleccionadas. "
        "No implica que el candidato posea todas estas competencias."
    )
    _render_jobs_reprocess_button()

    result = _current_job_analysis_result()
    market = _current_market_analysis()

    if result is None and market is None:
        st.info(EMPTY_RESULT_MESSAGE)
        return

    if result is not None:
        _render_job_analysis_message(result, has_market=market is not None)

    if market is None:
        _render_job_analysis_details(result)
        return

    _render_market_summary(market)
    _render_common_requirements(market.common_requirements)
    _render_market_skills(market)
    _render_market_keywords(market.keywords)
    _render_text_list("Diferenciadores", market.differentiators)
    _render_individual_job_analyses(market.job_analyses)
    _render_job_analysis_details(result)


def _render_jobs_reprocess_button() -> None:
    if not st.session_state.get(SessionKeys.VALIDATED_INPUT):
        return
    if st.button("Reprocesar vacantes", use_container_width=False):
        with st.status("Reprocesando vacantes...", expanded=False) as status:
            result = run_job_analysis_from_session(
                force=True,
                preserve_previous_on_failure=True,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if result.success:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = (
                    "El mercado objetivo fue reprocesado y validado correctamente."
                )
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Mercado objetivo reprocesado.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = JOB_REPROCESS_FAILURE_MESSAGE
                status.update(label="El reprocesamiento de vacantes falló.", state="error")


def _render_job_analysis_message(result: JobAnalysisResult, *, has_market: bool) -> None:
    if result.success:
        st.success("El mercado objetivo fue analizado y validado correctamente.")
        if result.reused_from_session:
            st.info("Se reutilizó el análisis de vacantes de esta sesión porque las descripciones no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible analizar las vacantes objetivo.")
        if has_market:
            st.warning(JOB_REPROCESS_FAILURE_MESSAGE)

    for warning in result.warnings:
        st.warning(warning)


def _render_market_summary(market: TargetMarketAnalysis) -> None:
    st.markdown("#### Resumen del mercado")
    with st.container(border=True):
        st.markdown(f"**Familia de roles:** {market.target_role_family}")
        st.markdown(f"**Seniority predominante:** {market.dominant_seniority}")
        st.markdown(f"**Resumen:** {market.market_summary}")
        if market.suggested_target_titles:
            st.markdown(f"**Títulos sugeridos:** {', '.join(market.suggested_target_titles)}")
    _render_text_list("Responsabilidades comunes", market.common_responsibilities)


def _render_common_requirements(requirements: list[JobRequirement]) -> None:
    st.markdown("#### Requisitos comunes")
    if not requirements:
        st.caption("No se detectaron requisitos comunes respaldados por más de una vacante.")
        return
    st.table(
        [
            {
                "Requisito": requirement.name,
                "Categoría": requirement.category,
                "Obligatorio": "Sí" if requirement.required else "No",
                "Prioridad": requirement.importance,
                "Keywords": ", ".join(requirement.exact_keywords),
            }
            for requirement in requirements
        ]
    )


def _render_market_skills(market: TargetMarketAnalysis) -> None:
    st.markdown("#### Skills")
    with st.container(border=True):
        _render_text_list("Técnicas", market.technical_skills)
        _render_text_list("Liderazgo", market.leadership_skills)
        _render_text_list("Negocio", market.business_skills)
        _render_text_list("Herramientas y tecnologías", market.tools_and_technologies)
        _render_text_list("Industrias", market.industries)


def _render_market_keywords(keywords: list[MarketKeyword]) -> None:
    st.markdown("#### Keywords")
    if not keywords:
        st.caption("No se detectaron keywords consolidadas.")
        return
    st.table(
        [
            {
                "Keyword": keyword.keyword,
                "Normalizada": keyword.normalized_keyword,
                "Frecuencia": keyword.frequency,
                "Vacantes": ", ".join(str(index) for index in keyword.job_indices),
                "Categoría": keyword.category,
                "Prioridad": keyword.priority,
            }
            for keyword in keywords
        ]
    )


def _render_individual_job_analyses(job_analyses: list[JobAnalysis]) -> None:
    st.markdown("#### Análisis individual")
    for job_analysis in sorted(job_analyses, key=lambda item: item.job_index):
        label = f"Vacante {job_analysis.job_index} — {job_analysis.title}"
        if job_analysis.company:
            label = f"{label} — {job_analysis.company}"
        with st.expander(label):
            st.markdown(f"**Seniority:** {job_analysis.inferred_seniority}")
            st.markdown(f"**Resumen:** {job_analysis.role_summary}")
            _render_text_list("Responsabilidades", job_analysis.responsibilities)
            _render_common_requirements(job_analysis.requirements)
            _render_text_list("Skills técnicas", job_analysis.technical_skills)
            _render_text_list("Soft skills", job_analysis.soft_skills)
            _render_text_list("Liderazgo", job_analysis.leadership_skills)
            _render_text_list("Herramientas", job_analysis.tools_and_technologies)
            _render_text_list("Educación", job_analysis.education_requirements)
            _render_text_list("Idiomas", job_analysis.language_requirements)
            _render_text_list("Certificaciones", job_analysis.certifications)
            _render_text_list("Keywords", job_analysis.exact_keywords)


def _render_job_analysis_details(result: JobAnalysisResult | None) -> None:
    if result is None:
        return
    with st.expander("Detalles del análisis"):
        st.caption(f"Modelo: {result.model_used or 'No disponible'}")
        st.caption(f"Tokens de entrada: {_token_label(result.input_tokens)}")
        st.caption(f"Tokens de salida: {_token_label(result.output_tokens)}")
        st.caption(f"Tokens totales: {_token_label(result.total_tokens)}")
        st.caption(f"Latencia: {_token_label(result.latency_ms)} ms")
        st.caption(f"Request ID: {result.request_id or 'No disponible'}")
        st.caption(f"Versión de prompt: {result.prompt_version or 'No disponible'}")
        st.caption(f"Reutilizado en sesión: {'Sí' if result.reused_from_session else 'No'}")
        count = len(result.market_analysis.job_analyses) if result.market_analysis else "No disponible"
        st.caption(f"Vacantes analizadas: {count}")
        if result.warnings:
            st.caption("Warnings:")
            for warning in result.warnings:
                st.caption(warning)
        if result.audit_findings:
            st.caption("Hallazgos de auditoría:")
            for finding in result.audit_findings:
                st.caption(finding)


def _render_compatibility_tab() -> None:
    st.markdown("### Compatibilidad con vacantes")
    st.warning(
        "Los scores representan alineación demostrable con las vacantes analizadas. "
        "No son probabilidades de contratación ni garantizan resultados."
    )

    profile = _current_profile()
    market = _current_market_analysis()
    result = _current_compatibility_result()
    report = _current_compatibility_report()

    _render_compatibility_reprocess_button(profile, market)

    if result is not None:
        _render_compatibility_message(result, has_report=report is not None)

    if report is None:
        if profile is None or market is None:
            st.info(COMPATIBILITY_MISSING_STAGES_MESSAGE)
        else:
            st.info("La compatibilidad aparecerá aquí cuando el análisis se complete correctamente.")
        _render_compatibility_details(result, report)
        return

    _render_compatibility_summary_cards(report)
    _render_global_compatibility_comparison(report)
    _render_job_compatibility_details(report.job_compatibilities)
    _render_compatibility_methodology()
    _render_compatibility_details(result, report)


def _render_compatibility_reprocess_button(
    profile: CandidateProfessionalProfile | None,
    market: TargetMarketAnalysis | None,
) -> None:
    if profile is None or market is None:
        return
    if st.button("Reprocesar compatibilidad", use_container_width=False):
        with st.status("Reprocesando compatibilidad...", expanded=False) as status:
            result = run_compatibility_from_session(
                force=True,
                preserve_previous_on_failure=True,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if result.success:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = "La compatibilidad fue reprocesada y validada correctamente."
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Compatibilidad reprocesada.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = COMPATIBILITY_REPROCESS_FAILURE_MESSAGE
                status.update(label="El reprocesamiento de compatibilidad falló.", state="error")


def _render_compatibility_message(result: CompatibilityAnalysisResult, *, has_report: bool) -> None:
    if result.success:
        st.success(
            "La compatibilidad fue calculada y validada correctamente.\n\n"
            "Revisa las evidencias y brechas antes de decidir cómo adaptar tu perfil o preparar una postulación."
        )
        if result.reused_from_session:
            st.info("Se reutilizó el análisis de compatibilidad porque la evidencia, las vacantes y la metodología no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible calcular la compatibilidad.")
        if has_report:
            st.warning(COMPATIBILITY_REPROCESS_FAILURE_MESSAGE)
    for warning in result.warnings:
        st.warning(warning)


def _render_compatibility_summary_cards(report: CompatibilityReport) -> None:
    st.markdown("#### Resumen comparativo")
    columns = st.columns(min(3, len(report.job_compatibilities)))
    for index, job in enumerate(report.job_compatibilities):
        with columns[index % len(columns)]:
            with st.container(border=True):
                st.markdown(f"**Vacante {job.job_index}**")
                st.markdown(f"**{job.job_title}**")
                if job.company:
                    st.caption(job.company)
                st.metric(
                    label="Score",
                    value=f"{job.compatibility_score:.1f} / 100",
                    delta=f"Compatibilidad {_band_label(job.compatibility_band).lower()}",
                    delta_color="off",
                )
                st.caption(f"Confianza: {job.confidence:.2f}")
                st.caption(f"Obligatorios cubiertos: {job.covered_required_count}/{job.total_required_count}")
                st.caption(f"Brechas críticas: {len(job.critical_gaps)}")


def _render_global_compatibility_comparison(report: CompatibilityReport) -> None:
    st.markdown("#### Comparación general")
    with st.container(border=True):
        if report.highest_compatibility_job_index is not None:
            st.markdown(
                "La vacante con mayor alineación demostrable es la "
                f"Vacante {report.highest_compatibility_job_index}. "
                "Esto no implica necesariamente que sea la mejor opción personal o laboral."
            )
        st.markdown(f"**Score promedio:** {report.average_compatibility_score:.1f} / 100")
        _render_text_list("Fortalezas comunes", report.common_strengths)
        _render_text_list("Brechas comunes", report.common_gaps)
        _render_text_list("Recomendaciones estratégicas", report.strategic_recommendations)


def _render_job_compatibility_details(jobs: list[JobCompatibility]) -> None:
    st.markdown("#### Detalle por vacante")
    for job in sorted(jobs, key=lambda item: item.job_index):
        label = f"Vacante {job.job_index} — {job.job_title} — {job.compatibility_score:.1f}/100"
        with st.expander(label, expanded=False):
            st.markdown(f"**Banda:** {_band_label(job.compatibility_band)}")
            st.markdown(f"**Confianza:** {job.confidence:.2f}")
            st.markdown(job.summary)
            _render_dimension_bars(job)
            _render_covered_requirements(job.requirement_matches)
            _render_gap_sections(job)
            _render_penalties(job)
            _render_text_list("Fortalezas principales", job.strengths)
            _render_text_list("Riesgos", job.risks)
            _render_text_list("Recomendaciones", job.recommendations)


def _render_dimension_bars(job: JobCompatibility) -> None:
    st.markdown("##### Seis dimensiones")
    rows = []
    for dimension in job.dimensions:
        if dimension.evaluated and dimension.score is not None:
            st.progress(dimension.score / 100)
            st.caption(
                f"{dimension.display_name}: {dimension.score:.1f} / 100 | "
                f"Peso: {dimension.effective_weight:.0%}"
            )
            score_label = f"{dimension.score:.1f}"
        else:
            st.caption(f"{dimension.display_name}: No solicitada por esta vacante")
            score_label = "No solicitada"
        rows.append(
            {
                "Dimensión": dimension.display_name,
                "Score": score_label,
                "Peso original": f"{dimension.original_weight:.0%}",
                "Peso efectivo": f"{dimension.effective_weight:.0%}",
            }
        )
    st.table(rows)


def _render_covered_requirements(matches: list[RequirementMatch]) -> None:
    st.markdown("##### Requisitos cubiertos")
    groups = [
        ("Completos", RequirementCoverage.FULL.value),
        ("Parciales", RequirementCoverage.PARTIAL.value),
        ("Indirectos", RequirementCoverage.INDIRECT.value),
    ]
    for title, coverage in groups:
        items = [match for match in matches if match.coverage == coverage]
        if not items:
            continue
        st.markdown(f"**{title}**")
        for index, match in enumerate(items):
            with st.expander(f"{match.requirement_name} — {_coverage_label(match.coverage)}"):
                _render_requirement_match(match, prefix=f"covered-{coverage}-{index}")


def _render_gap_sections(job: JobCompatibility) -> None:
    st.markdown("##### Brechas identificadas")
    if job.critical_gaps:
        st.markdown("**Brechas críticas**")
        for gap in job.critical_gaps:
            st.markdown(f"- {gap}")
    else:
        st.caption("No se identificaron brechas críticas con la evidencia disponible.")
    if job.other_gaps:
        st.markdown("**Otras brechas**")
        for gap in job.other_gaps:
            st.markdown(f"- {gap}")
    gap_matches = [
        match
        for match in job.requirement_matches
        if match.coverage
        in {
            RequirementCoverage.MISSING.value,
            RequirementCoverage.CONFLICT.value,
            RequirementCoverage.PARTIAL.value,
            RequirementCoverage.INDIRECT.value,
        }
    ]
    for index, match in enumerate(gap_matches):
        with st.expander(f"Detalle brecha — {match.requirement_name}"):
            _render_requirement_match(match, prefix=f"gap-{job.job_index}-{index}")


def _render_requirement_match(match: RequirementMatch, *, prefix: str) -> None:
    st.markdown(f"**Cobertura:** {_coverage_label(match.coverage)}")
    st.markdown(f"**Tipo:** {'Obligatorio' if match.required else 'Deseable'}")
    st.markdown(f"**Prioridad:** {match.priority}")
    st.markdown(f"**Evidencia:** {_status_label(match.evidence_status)}")
    st.markdown(f"**Explicación:** {match.explanation}")
    if match.matched_candidate_items:
        _render_text_list("Elementos del candidato relacionados", match.matched_candidate_items)
    if match.missing_elements:
        _render_text_list("Qué falta", match.missing_elements)
    if match.recommendation:
        st.markdown(f"**Recomendación:** {match.recommendation}")
    if match.candidate_evidence:
        with st.expander("Ver evidencia del candidato"):
            for evidence_index, evidence in enumerate(match.candidate_evidence):
                st.markdown(f"- **{_status_label(evidence.status)}:** {evidence.statement}")
                _render_references(
                    f"Referencias de evidencia {evidence_index + 1}",
                    evidence.references,
                    status=evidence.status,
                    confidence=evidence.confidence,
                    key=f"{prefix}-evidence-{evidence_index}",
                )


def _render_penalties(job: JobCompatibility) -> None:
    if not job.penalties:
        return
    st.markdown("##### Ajustes aplicados al score")
    for penalty in job.penalties:
        st.markdown(f"-{penalty.points:.1f} — {penalty.reason}")


def _render_compatibility_methodology() -> None:
    with st.expander("¿Cómo se calcula el score?"):
        st.markdown(
            "1. Se comparan los requisitos de cada vacante con la evidencia profesional estructurada.\n"
            "2. Se clasifica la cobertura como completa, parcial, indirecta, faltante, conflictiva o no aplicable.\n"
            "3. Cada requisito se agrupa en una de seis dimensiones.\n"
            "4. Se aplican pesos MVP por dimensión y se redistribuyen las dimensiones no solicitadas.\n"
            "5. Se aplican penalizaciones limitadas solo por brechas críticas permitidas.\n"
            "6. El resultado final queda en escala 0–100."
        )
        st.table(
            [
                {"Dimensión": dimension_id, "Peso MVP": f"{weight:.0%}"}
                for dimension_id, weight in COMPATIBILITY_DIMENSION_WEIGHTS.items()
            ]
        )
        st.caption(
            "El score no representa probabilidad de contratación. Es una metodología del producto para estimar "
            "alineación demostrable con la evidencia disponible."
        )


def _render_compatibility_details(
    result: CompatibilityAnalysisResult | None,
    report: CompatibilityReport | None,
) -> None:
    if result is None and report is None:
        return
    with st.expander("Detalles del análisis de compatibilidad"):
        if result is not None:
            st.caption(f"Modelo: {result.model_used or 'No disponible'}")
            st.caption(f"Tokens de entrada: {_token_label(result.input_tokens)}")
            st.caption(f"Tokens de salida: {_token_label(result.output_tokens)}")
            st.caption(f"Tokens totales: {_token_label(result.total_tokens)}")
            st.caption(f"Latencia: {_token_label(result.latency_ms)} ms")
            st.caption(f"Request ID: {result.request_id or 'No disponible'}")
            st.caption(f"Versión de prompt: {result.prompt_version or 'No disponible'}")
            st.caption(f"Versión de metodología: {result.methodology_version or COMPATIBILITY_METHODOLOGY_VERSION}")
            st.caption(f"Fingerprint reutilizado: {'Sí' if result.reused_from_session else 'No'}")
            if result.warnings:
                st.caption("Warnings:")
                for warning in result.warnings:
                    st.caption(warning)
            if result.audit_findings:
                st.caption("Hallazgos de auditoría:")
                for finding in result.audit_findings:
                    st.caption(finding)
        if report is not None:
            requirement_count = sum(len(job.requirement_matches) for job in report.job_compatibilities)
            st.caption(f"Número de vacantes: {len(report.job_compatibilities)}")
            st.caption(f"Número de requisitos: {requirement_count}")
            st.caption("Pesos efectivos por vacante:")
            for job in report.job_compatibilities:
                weights = ", ".join(
                    f"{dimension.display_name}: {dimension.effective_weight:.0%}"
                    for dimension in job.dimensions
                    if dimension.evaluated
                )
                st.caption(f"Vacante {job.job_index}: {weights}")


def _render_targeted_cv_tab() -> None:
    st.markdown("### CV optimizado por vacante")
    profile = _current_profile()
    market = _current_market_analysis()
    compatibility = _current_compatibility_report()
    if profile is None or market is None or compatibility is None:
        st.info(TARGETED_CV_MISSING_STAGES_MESSAGE)
        return

    _render_targeted_cv_summary(market)
    if st.button("Generar CVs para todas las vacantes", key="targeted_cv_generate_all", use_container_width=False):
        with st.status("Generando CVs por vacante...", expanded=False) as status:
            results = run_all_targeted_cv_generation_from_session(
                force=False,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            success_count = sum(1 for result in results if result.success)
            if success_count:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = f"{success_count} CV(s) por vacante generados correctamente."
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="CVs por vacante generados.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = "No fue posible generar CVs por vacante."
                status.update(label="No fue posible generar los CVs.", state="error")

    if st.button("Preparar descargas de CVs", key="targeted_cv_export_all", use_container_width=False):
        with st.status("Preparando descargas de CVs...", expanded=False) as status:
            export_result = build_targeted_cv_exports_from_session()
            if export_result["success"]:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = TARGETED_CV_EXPORT_SUCCESS_MESSAGE
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Descargas de CVs listas.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = TARGETED_CV_EXPORT_FAILURE_MESSAGE
                status.update(label="No fue posible preparar todas las descargas.", state="error")
                for error in export_result["errors"]:
                    st.error(error)

    for job in sorted(market.job_analyses, key=lambda item: item.job_index):
        job_compatibility = next(
            (item for item in compatibility.job_compatibilities if item.job_index == job.job_index),
            None,
        )
        _render_targeted_cv_card(job, job_compatibility)


def _render_targeted_cv_summary(market: TargetMarketAnalysis) -> None:
    cvs = _current_targeted_cvs()
    audits = _current_targeted_cv_audits()
    ats_audits = _current_targeted_cv_ats_audits()
    job_count = len(market.job_analyses)
    generated_count = len(cvs)
    valid_count = sum(1 for audit in audits.values() if audit.passed)
    warning_count = sum(
        1
        for audit in audits.values()
        for finding in audit.findings
        if finding.severity == "warning"
    )
    columns = st.columns(4)
    columns[0].metric("Vacantes", job_count)
    columns[1].metric("CVs generados", generated_count)
    columns[2].metric("CVs válidos", valid_count)
    best_ats = max((audit.overall_score for audit in ats_audits.values()), default=0)
    columns[3].metric("Mejor score ATS CV", f"{best_ats:.0f}")
    if generated_count < job_count:
        st.caption(f"Pendientes: {job_count - generated_count}")
    if warning_count:
        st.caption(f"Advertencias de revisión: {warning_count}")


def _render_targeted_cv_card(job: JobAnalysis, job_compatibility: JobCompatibility | None) -> None:
    cv = _current_targeted_cv(job.job_index)
    result = _current_targeted_cv_generation_result(job.job_index)
    ats_audit = _current_targeted_cv_ats_audit(job.job_index)
    audit = _current_targeted_cv_audit(job.job_index)
    company = f" | {job.company}" if job.company else ""
    with st.expander(f"Vacante {job.job_index}: {job.title}{company}", expanded=cv is not None):
        columns = st.columns(4)
        columns[0].metric("Compatibilidad", f"{job_compatibility.compatibility_score:.0f}" if job_compatibility else "N/D")
        columns[1].metric("Estado CV", "Generado" if cv else "Pendiente")
        columns[2].metric("Validación", "Válido" if audit and audit.passed else "Pendiente")
        columns[3].metric("ATS CV", f"{ats_audit.overall_score:.0f}" if ats_audit else "N/D")

        button_label = "Regenerar CV" if cv else "Generar CV"
        if st.button(button_label, key=f"targeted_cv_generate_{job.job_index}", use_container_width=False):
            with st.status(f"Generando CV para vacante {job.job_index}...", expanded=False) as status:
                result = run_targeted_cv_generation_from_session(
                    job.job_index,
                    force=cv is not None,
                    preserve_previous_on_failure=True,
                    status_callback=lambda label: status.update(label=label, state="running"),
                )
                if result.success:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = TARGETED_CV_SUCCESS_MESSAGE
                    st.session_state[SessionKeys.PROCESS_ERROR] = None
                    status.update(label="CV por vacante listo.", state="complete")
                else:
                    st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                    st.session_state[SessionKeys.PROCESS_ERROR] = TARGETED_CV_REPROCESS_FAILURE_MESSAGE if cv else result.user_message
                    status.update(label="No fue posible generar el CV.", state="error")

        result = _current_targeted_cv_generation_result(job.job_index)
        _render_targeted_cv_generation_message(result, cv is not None)
        cv = _current_targeted_cv(job.job_index)
        if cv is None:
            st.caption("El CV específico aparecerá aquí cuando se genere correctamente.")
            return

        _render_targeted_cv_editor(cv)
        validation = _current_targeted_cv_edit_validation(job.job_index)
        if validation:
            _render_targeted_cv_validation(validation)
        _render_targeted_cv_audit_details(audit, ats_audit)
        col_validate, col_export = st.columns(2)
        with col_validate:
            if st.button("Validar cambios del CV", key=f"targeted_cv_validate_{job.job_index}", use_container_width=True):
                export_result = build_targeted_cv_exports_from_session(job.job_index)
                if export_result["success"]:
                    st.success("Los cambios del CV son válidos.")
                else:
                    st.error("Los cambios del CV requieren revisión antes de exportar.")
        with col_export:
            if st.button("Preparar descargas", key=f"targeted_cv_export_{job.job_index}", use_container_width=True):
                export_result = build_targeted_cv_exports_from_session(job.job_index)
                if export_result["success"]:
                    st.success(TARGETED_CV_EXPORT_SUCCESS_MESSAGE)
                else:
                    st.error(TARGETED_CV_EXPORT_FAILURE_MESSAGE)
                    for error in export_result["errors"]:
                        st.caption(error)
        _render_targeted_cv_job_downloads(cv)


def _render_targeted_cv_generation_message(result: TargetedCVGenerationResult | None, has_cv: bool) -> None:
    if result is None:
        return
    if result.success:
        st.success(TARGETED_CV_SUCCESS_MESSAGE)
        if result.reused_from_session:
            st.info("Se reutilizó el CV específico porque los insumos no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible generar el CV específico por vacante.")
        if result.error_category:
            st.caption(f"Categoría técnica: {result.error_category}")
        if has_cv:
            st.warning(TARGETED_CV_REPROCESS_FAILURE_MESSAGE)
    for warning in result.warnings:
        st.warning(warning)


def _render_targeted_cv_editor(cv: TargetedCV) -> None:
    edit_state = _ensure_targeted_cv_edit_state(cv)
    st.markdown("#### Editor")
    st.text_input(
        "Título profesional",
        value=edit_state["professional_title"],
        key=_targeted_cv_edit_key(cv.target_job_index, "professional_title"),
    )
    st.text_area(
        "Resumen profesional",
        value=edit_state["summary"],
        key=_targeted_cv_edit_key(cv.target_job_index, "summary"),
        height=160,
    )
    skill_options = [skill.name for skill in sorted(cv.skills, key=lambda item: item.priority)]
    st.multiselect(
        "Skills seleccionadas",
        options=skill_options,
        default=[skill for skill in edit_state["selected_skills"] if skill in skill_options],
        key=_targeted_cv_edit_key(cv.target_job_index, "selected_skills"),
    )
    for index, entry in enumerate(cv.experience):
        with st.expander(f"{entry.employer} - {entry.source_role_title}", expanded=entry.included):
            st.checkbox(
                "Incluir experiencia",
                value=edit_state["experience"][index]["included"],
                key=_targeted_cv_edit_key(cv.target_job_index, f"experience_included_{index}"),
            )
            st.text_input(
                "Cargo mostrado",
                value=edit_state["experience"][index]["display_role_title"],
                key=_targeted_cv_edit_key(cv.target_job_index, f"experience_title_{index}"),
            )
            for bullet_index, bullet_text in enumerate(edit_state["experience"][index]["bullets"]):
                st.text_area(
                    f"Bullet {bullet_index + 1}",
                    value=bullet_text,
                    key=_targeted_cv_edit_key(cv.target_job_index, f"experience_bullet_{index}_{bullet_index}"),
                    height=90,
                )
    _render_targeted_cv_visibility_controls(cv, edit_state)
    _sync_targeted_cv_edit_state(cv, edit_state)


def _render_targeted_cv_visibility_controls(cv: TargetedCV, edit_state: dict) -> None:
    if cv.education:
        st.multiselect(
            "Educación visible",
            options=list(range(len(cv.education))),
            default=edit_state["education_visible"],
            format_func=lambda index: cv.education[index].text,
            key=_targeted_cv_edit_key(cv.target_job_index, "education_visible"),
        )
    if cv.certifications:
        st.multiselect(
            "Certificaciones visibles",
            options=list(range(len(cv.certifications))),
            default=edit_state["certifications_visible"],
            format_func=lambda index: cv.certifications[index].text,
            key=_targeted_cv_edit_key(cv.target_job_index, "certifications_visible"),
        )
    if cv.languages:
        st.multiselect(
            "Idiomas visibles",
            options=list(range(len(cv.languages))),
            default=edit_state["languages_visible"],
            format_func=lambda index: cv.languages[index].text,
            key=_targeted_cv_edit_key(cv.target_job_index, "languages_visible"),
        )


def _render_targeted_cv_validation(validation: TargetedCVEditableValidationResult) -> None:
    if validation.passed:
        st.success("Los cambios del CV pasaron la validación local.")
    else:
        st.error("Los cambios del CV no pasaron la validación local.")
    for finding in validation.findings:
        if finding.severity == "error":
            st.caption(f"error: {finding.path}: {finding.message}")
    for warning in validation.warnings:
        st.caption(f"warning: {warning}")


def _render_targeted_cv_audit_details(
    audit: TargetedCVAuditResult | None,
    ats_audit: TargetedCVATSAudit | None,
) -> None:
    with st.expander("Auditoría del CV específico"):
        if audit is None:
            st.caption("Auditoría no disponible.")
        else:
            st.caption(f"Auditoría local: {'válida' if audit.passed else 'requiere revisión'}")
            for finding in audit.findings:
                st.caption(f"{finding.severity}: {finding.path}: {finding.message}")
        if ats_audit is not None:
            st.caption(f"Score ATS CV: {ats_audit.overall_score:.1f}")
            st.table(
                [
                    {
                        "Componente": component,
                        "Peso": f"{ats_audit.weights[component]:.0%}",
                        "Score": f"{score:.1f}",
                    }
                    for component, score in ats_audit.component_scores.items()
                ]
            )
            if ats_audit.missing_supported_keywords:
                _render_text_list("Keywords respaldadas faltantes", ats_audit.missing_supported_keywords)


def _render_targeted_cv_job_downloads(cv: TargetedCV) -> None:
    markdown = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_MARKDOWN_BYTES, cv.target_job_index)
    docx = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_DOCX_BYTES, cv.target_job_index)
    pdf = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_PDF_BYTES, cv.target_job_index)
    if not all([markdown, docx, pdf]):
        st.caption("Prepara las descargas para habilitar los archivos de esta vacante.")
        return
    st.download_button(
        "Descargar CV Markdown",
        data=markdown,
        file_name=targeted_cv_download_filename(cv, "md"),
        mime="text/markdown",
        key=f"targeted_cv_download_md_{cv.target_job_index}",
    )
    st.download_button(
        "Descargar CV DOCX",
        data=docx,
        file_name=targeted_cv_download_filename(cv, "docx"),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=f"targeted_cv_download_docx_{cv.target_job_index}",
    )
    st.download_button(
        "Descargar CV PDF",
        data=pdf,
        file_name=targeted_cv_download_filename(cv, "pdf"),
        mime="application/pdf",
        key=f"targeted_cv_download_pdf_{cv.target_job_index}",
    )


def _ensure_targeted_cv_edit_state(cv: TargetedCV) -> dict:
    fingerprints = st.session_state.get(SessionKeys.TARGETED_CV_INPUT_FINGERPRINTS) or {}
    fingerprint = fingerprints.get(str(cv.target_job_index))
    edit_states = st.session_state.get(SessionKeys.TARGETED_CV_EDIT_STATES) or {}
    edit_state = edit_states.get(str(cv.target_job_index))
    if not edit_state or edit_state.get("_source_fingerprint") != fingerprint:
        edit_state = build_targeted_cv_edit_state(cv)
        edit_state["_source_fingerprint"] = fingerprint
        edit_states[str(cv.target_job_index)] = edit_state
        st.session_state[SessionKeys.TARGETED_CV_EDIT_STATES] = edit_states
        _reset_targeted_cv_edit_widgets(cv)
    return edit_state


def _reset_targeted_cv_edit_widgets(cv: TargetedCV) -> None:
    prefix = f"targeted_cv_edit_{cv.target_job_index}_"
    for key in list(st.session_state.keys()):
        if str(key).startswith(prefix):
            del st.session_state[key]


def _sync_targeted_cv_edit_state(cv: TargetedCV, edit_state: dict) -> None:
    current = {
        "edited": False,
        "_source_fingerprint": edit_state.get("_source_fingerprint"),
        "professional_title": st.session_state.get(
            _targeted_cv_edit_key(cv.target_job_index, "professional_title"),
            edit_state["professional_title"],
        ),
        "summary": st.session_state.get(_targeted_cv_edit_key(cv.target_job_index, "summary"), edit_state["summary"]),
        "selected_skills": st.session_state.get(
            _targeted_cv_edit_key(cv.target_job_index, "selected_skills"),
            edit_state["selected_skills"],
        ),
        "experience": [],
        "education_visible": st.session_state.get(
            _targeted_cv_edit_key(cv.target_job_index, "education_visible"),
            edit_state["education_visible"],
        ),
        "certifications_visible": st.session_state.get(
            _targeted_cv_edit_key(cv.target_job_index, "certifications_visible"),
            edit_state["certifications_visible"],
        ),
        "languages_visible": st.session_state.get(
            _targeted_cv_edit_key(cv.target_job_index, "languages_visible"),
            edit_state["languages_visible"],
        ),
    }
    for index, item in enumerate(edit_state["experience"]):
        current["experience"].append(
            {
                "included": st.session_state.get(
                    _targeted_cv_edit_key(cv.target_job_index, f"experience_included_{index}"),
                    item["included"],
                ),
                "display_role_title": st.session_state.get(
                    _targeted_cv_edit_key(cv.target_job_index, f"experience_title_{index}"),
                    item["display_role_title"],
                ),
                "bullets": [
                    st.session_state.get(
                        _targeted_cv_edit_key(cv.target_job_index, f"experience_bullet_{index}_{bullet_index}"),
                        bullet_text,
                    )
                    for bullet_index, bullet_text in enumerate(item["bullets"])
                ],
            }
        )
    original = build_targeted_cv_edit_state(cv)
    current["edited"] = _targeted_cv_edit_state_without_metadata(current) != _targeted_cv_edit_state_without_metadata(original)
    edit_states = st.session_state.get(SessionKeys.TARGETED_CV_EDIT_STATES) or {}
    previous = edit_states.get(str(cv.target_job_index))
    if isinstance(previous, dict) and _targeted_cv_edit_state_without_metadata(previous) != _targeted_cv_edit_state_without_metadata(current):
        _targeted_cv_dict_set(SessionKeys.TARGETED_CV_MARKDOWN_BYTES, cv.target_job_index, None)
        _targeted_cv_dict_set(SessionKeys.TARGETED_CV_DOCX_BYTES, cv.target_job_index, None)
        _targeted_cv_dict_set(SessionKeys.TARGETED_CV_PDF_BYTES, cv.target_job_index, None)
        _targeted_cv_dict_set(SessionKeys.TARGETED_CV_EXPORT_FINGERPRINTS, cv.target_job_index, None)
        st.session_state[SessionKeys.TARGETED_CV_ZIP_BYTES] = None
        _clear_application_communication_after_targeted_cv_edit(cv.target_job_index)
    edit_states[str(cv.target_job_index)] = current
    st.session_state[SessionKeys.TARGETED_CV_EDIT_STATES] = edit_states
    if current["edited"]:
        st.info("CV editado por el usuario")


def _targeted_cv_edit_state_without_metadata(state: dict) -> dict:
    return {key: value for key, value in state.items() if key not in {"edited", "_source_fingerprint"}}


def _targeted_cv_edit_key(job_index: int, name: str) -> str:
    return f"targeted_cv_edit_{job_index}_{name}"


def _clear_application_communication_after_targeted_cv_edit(job_index: int) -> None:
    for key in (
        SessionKeys.APPLICATION_COMMUNICATION_RESULTS,
        SessionKeys.APPLICATION_COMMUNICATION_KITS,
        SessionKeys.APPLICATION_COMMUNICATION_AUDITS,
        SessionKeys.APPLICATION_COMMUNICATION_REDUNDANCY_AUDITS,
        SessionKeys.APPLICATION_COMMUNICATION_INPUT_FINGERPRINTS,
        SessionKeys.APPLICATION_COMMUNICATION_EDIT_STATES,
        SessionKeys.APPLICATION_COMMUNICATION_EDIT_VALIDATIONS,
        SessionKeys.APPLICATION_COMMUNICATION_EXPORT_FINGERPRINTS,
        SessionKeys.APPLICATION_COMMUNICATION_MARKDOWN_BYTES,
        SessionKeys.APPLICATION_COMMUNICATION_TXT_BYTES,
        SessionKeys.APPLICATION_COMMUNICATION_DOCX_BYTES,
        SessionKeys.APPLICATION_COMMUNICATION_PDF_BYTES,
    ):
        _targeted_cv_dict_set(key, job_index, None)
    st.session_state[SessionKeys.APPLICATION_COMMUNICATION_ZIP_BYTES] = None


def _render_downloads_tab() -> None:
    st.markdown("### Descargas")
    output = _current_linkedin_profile_output()
    market = _current_market_analysis()
    compatibility = _current_compatibility_report()
    profile = _current_profile()
    audit = _current_final_audit_report()
    stored_banner = _current_banner_render_result()
    stored_bytes = st.session_state.get(SessionKeys.BANNER_IMAGE_BYTES)

    if output is None and market is None and compatibility is None and audit is None and not stored_bytes:
        st.info(EMPTY_RESULT_MESSAGE)
        return

    st.caption("Las descargas disponibles se generan desde los resultados validados de esta sesión.")
    _render_final_package_section(profile, market, output, compatibility, audit, stored_banner, stored_bytes)
    st.divider()
    _render_targeted_cv_downloads_section()
    st.divider()
    render_application_communication_downloads_section()
    st.divider()
    st.markdown("#### Descargas individuales existentes")
    _render_banner_download_section(output, stored_banner, stored_bytes)
    _render_markdown_downloads(output, market, compatibility)


def _render_targeted_cv_downloads_section() -> None:
    st.markdown("#### CVs por vacante")
    cvs = _current_targeted_cvs()
    if not cvs:
        st.caption("Los CVs por vacante aparecerán aquí cuando se generen desde la pestaña CV por vacante.")
        return
    if st.button("Preparar descargas de CVs por vacante", key="downloads_targeted_cv_export_all", use_container_width=False):
        export_result = build_targeted_cv_exports_from_session()
        if export_result["success"]:
            st.success(TARGETED_CV_EXPORT_SUCCESS_MESSAGE)
        else:
            st.error(TARGETED_CV_EXPORT_FAILURE_MESSAGE)
            for error in export_result["errors"]:
                st.caption(error)

    rows = []
    for index, cv in sorted(cvs.items()):
        rows.append(
            {
                "Vacante": index,
                "Título": cv.target_job_title,
                "Markdown": _format_targeted_cv_bytes(SessionKeys.TARGETED_CV_MARKDOWN_BYTES, index),
                "DOCX": _format_targeted_cv_bytes(SessionKeys.TARGETED_CV_DOCX_BYTES, index),
                "PDF": _format_targeted_cv_bytes(SessionKeys.TARGETED_CV_PDF_BYTES, index),
            }
        )
    st.table(rows)
    zip_bytes = st.session_state.get(SessionKeys.TARGETED_CV_ZIP_BYTES)
    if zip_bytes:
        st.download_button(
            "Descargar ZIP de CVs por vacante",
            data=zip_bytes,
            file_name=TARGETED_CV_ZIP_FILENAME,
            mime="application/zip",
            key="downloads_targeted_cv_zip",
        )
    for index, cv in sorted(cvs.items()):
        markdown = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_MARKDOWN_BYTES, index)
        docx = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_DOCX_BYTES, index)
        pdf = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_PDF_BYTES, index)
        if not all([markdown, docx, pdf]):
            continue
        st.download_button(
            f"Vacante {index} - CV Markdown",
            data=markdown,
            file_name=targeted_cv_download_filename(cv, "md"),
            mime="text/markdown",
            key=f"downloads_targeted_cv_md_{index}",
        )
        st.download_button(
            f"Vacante {index} - CV DOCX",
            data=docx,
            file_name=targeted_cv_download_filename(cv, "docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"downloads_targeted_cv_docx_{index}",
        )
        st.download_button(
            f"Vacante {index} - CV PDF",
            data=pdf,
            file_name=targeted_cv_download_filename(cv, "pdf"),
            mime="application/pdf",
            key=f"downloads_targeted_cv_pdf_{index}",
        )


def _render_final_package_section(
    profile: CandidateProfessionalProfile | None,
    market: TargetMarketAnalysis | None,
    output: LinkedInProfileOutput | None,
    compatibility: CompatibilityReport | None,
    audit: AuditReport | None,
    stored_banner: BannerRenderResult | None,
    stored_bytes: bytes | None,
) -> None:
    st.markdown("#### Entregables")
    banner_available = _current_banner_available(output, stored_banner, stored_bytes)
    _render_final_package_status(profile, market, output, compatibility, audit, banner_available)
    if audit is None or not audit.success:
        st.info("Para generar el paquete final es necesario completar primero la auditoría integral.")
    result = _current_final_package_build_result()
    package_exists = _final_package_bytes_available()
    button_label = "Regenerar paquete final" if package_exists else "Generar paquete final"
    disabled = profile is None or market is None or output is None or compatibility is None or audit is None or not audit.success
    if st.button(button_label, key="generate_final_package", disabled=disabled, use_container_width=False):
        with st.status("Generando paquete final...", expanded=False) as status:
            result = build_final_package_from_session(
                force=False,
                status_callback=lambda label: status.update(label=label, state="running"),
            )
            if result.success:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = "El paquete profesional fue generado y validado correctamente."
                st.session_state[SessionKeys.PROCESS_ERROR] = None
                status.update(label="Paquete profesional listo.", state="complete")
            else:
                st.session_state[SessionKeys.PROCESS_MESSAGE] = None
                st.session_state[SessionKeys.PROCESS_ERROR] = result.user_message
                status.update(label="No fue posible generar el paquete.", state="error")

    result = _current_final_package_build_result()
    _render_final_package_result(result)
    if _final_package_bytes_available():
        _render_final_package_downloads(banner_available, stored_bytes)


def _render_final_package_status(
    profile: CandidateProfessionalProfile | None,
    market: TargetMarketAnalysis | None,
    output: LinkedInProfileOutput | None,
    compatibility: CompatibilityReport | None,
    audit: AuditReport | None,
    banner_available: bool,
) -> None:
    rows = [
        {"Requisito": "Candidato válido", "Estado": _check_label(profile is not None)},
        {"Requisito": "Mercado válido", "Estado": _check_label(market is not None)},
        {"Requisito": "Perfil LinkedIn válido", "Estado": _check_label(output is not None)},
        {"Requisito": "Compatibilidad válida", "Estado": _check_label(compatibility is not None)},
        {"Requisito": "Auditoría válida", "Estado": _check_label(audit is not None and audit.success)},
        {"Requisito": "Banner disponible", "Estado": _check_label(banner_available)},
    ]
    st.table(rows)


def _render_final_package_result(result: FinalPackageBuildResult | None) -> None:
    if result is None:
        st.caption("El paquete final se generará solo cuando pulses el botón.")
        return
    if result.success and result.package is not None:
        if FINAL_PACKAGE_REUSE_MESSAGE in result.warnings:
            st.info(FINAL_PACKAGE_REUSE_MESSAGE)
        else:
            st.success("El paquete profesional fue generado y validado correctamente.")
        package = result.package
        st.markdown("**Vista general**")
        st.table(
            [
                {"Campo": "Nombre del paquete", "Valor": package.package_title},
                {"Campo": "Idioma", "Valor": package.output_language},
                {"Campo": "Fuente de contenido", "Valor": package.content_source},
                {"Campo": "Fecha", "Valor": package.generated_at.isoformat(timespec="seconds")},
                {"Campo": "Banner incluido", "Valor": "Sí" if package.banner_included else "No"},
            ]
        )
        st.markdown("**Resumen ejecutivo**")
        st.write(package.executive_summary)
        st.markdown("**Secciones incluidas**")
        st.write(
            [
                "Portada",
                "Resumen ejecutivo",
                "Perfil de LinkedIn",
                "Banner textual",
                "Headline",
                "About",
                "Experiencia profesional",
                "Skills priorizadas",
                "Keywords ATS",
                "Compatibilidad por vacante",
                "Fortalezas",
                "Brechas",
                "Recomendaciones",
                "Auditoría LinkedIn",
                "Auditoría ATS",
                "Metodología y disclaimer",
            ]
        )
    else:
        st.error(result.user_message or "No fue posible generar el paquete profesional.")
    for finding in result.findings:
        st.error(finding)
    for warning in result.warnings:
        if warning != FINAL_PACKAGE_REUSE_MESSAGE:
            st.warning(warning)


def _render_final_package_downloads(banner_available: bool, stored_banner_bytes: bytes | None) -> None:
    st.markdown("#### Descargas del paquete final")
    rows = [
        {"Archivo": INDIVIDUAL_MARKDOWN_FILENAME, "Tamaño": _format_bytes(SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES)},
        {"Archivo": INDIVIDUAL_HTML_FILENAME, "Tamaño": _format_bytes(SessionKeys.FINAL_PACKAGE_HTML_BYTES)},
        {"Archivo": INDIVIDUAL_DOCX_FILENAME, "Tamaño": _format_bytes(SessionKeys.FINAL_PACKAGE_DOCX_BYTES)},
        {"Archivo": INDIVIDUAL_PDF_FILENAME, "Tamaño": _format_bytes(SessionKeys.FINAL_PACKAGE_PDF_BYTES)},
        {"Archivo": FINAL_ZIP_FILENAME, "Tamaño": _format_bytes(SessionKeys.FINAL_PACKAGE_ZIP_BYTES)},
    ]
    if banner_available and stored_banner_bytes:
        rows.append({"Archivo": DEFAULT_BANNER_FILENAME, "Tamaño": f"{len(stored_banner_bytes) / 1024:.1f} KB"})
    st.table(rows)
    st.download_button(
        label="Descargar Markdown",
        data=st.session_state[SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES],
        file_name=INDIVIDUAL_MARKDOWN_FILENAME,
        mime="text/markdown",
        key="final_package_markdown",
    )
    st.download_button(
        label="Descargar HTML",
        data=st.session_state[SessionKeys.FINAL_PACKAGE_HTML_BYTES],
        file_name=INDIVIDUAL_HTML_FILENAME,
        mime="text/html",
        key="final_package_html",
    )
    st.download_button(
        label="Descargar DOCX",
        data=st.session_state[SessionKeys.FINAL_PACKAGE_DOCX_BYTES],
        file_name=INDIVIDUAL_DOCX_FILENAME,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key="final_package_docx",
    )
    st.download_button(
        label="Descargar PDF",
        data=st.session_state[SessionKeys.FINAL_PACKAGE_PDF_BYTES],
        file_name=INDIVIDUAL_PDF_FILENAME,
        mime="application/pdf",
        key="final_package_pdf",
    )
    if banner_available and stored_banner_bytes:
        st.download_button(
            label="Descargar banner PNG",
            data=stored_banner_bytes,
            file_name=DEFAULT_BANNER_FILENAME,
            mime="image/png",
            key="final_package_banner_png",
        )
    st.download_button(
        label="Descargar paquete completo ZIP",
        data=st.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES],
        file_name=FINAL_ZIP_FILENAME,
        mime="application/zip",
        key="final_package_zip",
    )


def _current_banner_available(
    output: LinkedInProfileOutput | None,
    stored_result: BannerRenderResult | None,
    stored_bytes: bytes | None,
) -> bool:
    if not stored_result or not stored_result.success or not stored_bytes:
        return False
    if output is None:
        return True
    edit_state = _ensure_linkedin_edit_state(output)
    current_payload = _current_banner_render_payload(edit_state)
    current_fingerprint = _current_banner_fingerprint(current_payload)
    return bool(current_fingerprint and stored_result.fingerprint == current_fingerprint)


def _final_package_bytes_available() -> bool:
    return all(
        st.session_state.get(key)
        for key in (
            SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES,
            SessionKeys.FINAL_PACKAGE_HTML_BYTES,
            SessionKeys.FINAL_PACKAGE_DOCX_BYTES,
            SessionKeys.FINAL_PACKAGE_PDF_BYTES,
            SessionKeys.FINAL_PACKAGE_ZIP_BYTES,
        )
    )


def _format_bytes(session_key: str) -> str:
    data = st.session_state.get(session_key) or b""
    return f"{len(data) / 1024:.1f} KB"


def _render_banner_download_section(
    output: LinkedInProfileOutput | None,
    stored_result: BannerRenderResult | None,
    stored_bytes: bytes | None,
) -> None:
    st.markdown("#### Banner PNG")
    if not stored_result or not stored_result.success or not stored_bytes:
        if output is None:
            st.caption("El banner aparecerá aquí cuando exista un perfil de LinkedIn generado y un PNG válido.")
        else:
            st.info("Genera el banner PNG desde la pestaña Perfil LinkedIn para habilitar esta descarga.")
        return

    is_current = True
    if output is not None:
        edit_state = _ensure_linkedin_edit_state(output)
        current_payload = _current_banner_render_payload(edit_state)
        current_fingerprint = _current_banner_fingerprint(current_payload)
        is_current = bool(current_fingerprint and stored_result.fingerprint == current_fingerprint)
    if not is_current:
        st.warning("El contenido editable del banner cambió. Regenera el PNG antes de descargarlo desde esta pestaña.")
        return

    st.download_button(
        label="Descargar banner PNG",
        data=stored_bytes,
        file_name=stored_result.filename or DEFAULT_BANNER_FILENAME,
        mime="image/png",
        key="downloads_banner_png",
    )


def _render_markdown_downloads(
    output: LinkedInProfileOutput | None,
    market: TargetMarketAnalysis | None,
    compatibility: CompatibilityReport | None,
) -> None:
    st.markdown("#### Documentos Markdown")
    any_download = False
    if output is not None:
        edit_state = _ensure_linkedin_edit_state(output)
        st.download_button(
            label="Descargar perfil LinkedIn optimizado (.md)",
            data=_linkedin_profile_markdown(output, edit_state).encode("utf-8"),
            file_name="astrogato-vector-perfil-linkedin.md",
            mime="text/markdown",
            key="downloads_linkedin_profile_md",
        )
        any_download = True
    if market is not None:
        st.download_button(
            label="Descargar mercado objetivo (.md)",
            data=_market_analysis_markdown(market).encode("utf-8"),
            file_name="astrogato-vector-mercado-objetivo.md",
            mime="text/markdown",
            key="downloads_market_md",
        )
        any_download = True
    if compatibility is not None:
        st.download_button(
            label="Descargar compatibilidad (.md)",
            data=_compatibility_report_markdown(compatibility).encode("utf-8"),
            file_name="astrogato-vector-compatibilidad.md",
            mime="text/markdown",
            key="downloads_compatibility_md",
        )
        any_download = True
    if not any_download:
        st.caption("Todavía no hay documentos Markdown disponibles.")


def _linkedin_profile_markdown(output: LinkedInProfileOutput, edit_state: dict) -> str:
    banner = _current_banner_render_payload(edit_state)
    headline = st.session_state.get(_edit_key("headline"), edit_state["headline"])
    about = st.session_state.get(_edit_key("about"), edit_state["about"])
    lines = [
        "# Perfil de LinkedIn optimizado",
        "",
        "## Banner",
        "",
        f"- Línea principal: {banner['primary_line']}",
        f"- Especialidades: {banner['specialty_line']}",
        f"- Línea de apoyo: {banner['supporting_line'] or ''}",
        f"- Concepto visual: {banner['visual_concept'] or ''}",
        f"- Plantilla: {BANNER_TEMPLATE_LABELS.get(banner['template_id'], banner['template_id'])}",
        "",
        "## Headline",
        "",
        headline,
        "",
        "## About",
        "",
        about,
        "",
        "## Experiencia",
        "",
    ]
    for index, experience in enumerate(output.experience):
        title = st.session_state.get(
            _edit_key(f"experience_title_{index}"),
            edit_state["experience"][index]["suggested_role_title"],
        )
        text = st.session_state.get(
            _edit_key(f"experience_text_{index}"),
            edit_state["experience"][index]["rewritten_text"],
        )
        lines.extend([f"### {experience.employer} - {title}", "", text, ""])
    selected_skills = st.session_state.get(_edit_key("selected_skills"), edit_state["selected_skills"])
    selected_keywords = st.session_state.get(_edit_key("selected_keywords"), edit_state["selected_keywords"])
    lines.extend(
        [
            "## Skills seleccionadas",
            "",
            *_markdown_bullets(selected_skills),
            "",
            "## Keywords ATS seleccionadas",
            "",
            *_markdown_bullets(selected_keywords),
            "",
            "## Notas de revisión",
            "",
            *_markdown_bullets(output.global_review_notes),
            "",
        ]
    )
    return "\n".join(lines)


def _market_analysis_markdown(market: TargetMarketAnalysis) -> str:
    lines = [
        "# Mercado objetivo",
        "",
        f"- Familia de roles: {market.target_role_family}",
        f"- Seniority predominante: {market.dominant_seniority}",
        "",
        market.market_summary,
        "",
        "## Responsabilidades comunes",
        "",
        *_markdown_bullets(market.common_responsibilities),
        "",
        "## Requisitos comunes",
        "",
    ]
    for requirement in market.common_requirements:
        lines.append(
            f"- {requirement.name} ({'obligatorio' if requirement.required else 'deseable'}, {requirement.importance})"
        )
    lines.extend(["", "## Vacantes", ""])
    for job in market.job_analyses:
        lines.extend(
            [
                f"### Vacante {job.job_index}: {job.title}",
                "",
                f"- Empresa: {job.company or 'No proporcionada'}",
                f"- Seniority: {job.inferred_seniority}",
                "",
                job.role_summary,
                "",
                "Requisitos:",
                "",
            ]
        )
        for requirement in job.requirements:
            lines.append(
                f"- {requirement.name} ({'obligatorio' if requirement.required else 'deseable'}, {requirement.importance})"
            )
        lines.append("")
    return "\n".join(lines)


def _compatibility_report_markdown(report: CompatibilityReport) -> str:
    lines = [
        "# Compatibilidad con vacantes",
        "",
        report.disclaimer,
        "",
        f"- Vacante con mayor alineación: {report.highest_compatibility_job_index}",
        f"- Score promedio: {report.average_compatibility_score:.1f}",
        "",
    ]
    for job in report.job_compatibilities:
        lines.extend(
            [
                f"## Vacante {job.job_index}: {job.job_title}",
                "",
                f"- Score: {job.compatibility_score:.1f}/100",
                f"- Banda: {_band_label(job.compatibility_band)}",
                f"- Confianza: {job.confidence:.2f}",
                f"- Obligatorios cubiertos: {job.covered_required_count}/{job.total_required_count}",
                "",
                job.summary,
                "",
                "### Dimensiones",
                "",
            ]
        )
        for dimension in job.dimensions:
            score = "No solicitada" if dimension.score is None else f"{dimension.score:.1f}"
            lines.append(f"- {dimension.display_name}: {score} | peso efectivo {dimension.effective_weight:.0%}")
        lines.extend(["", "### Fortalezas", "", *_markdown_bullets(job.strengths), ""])
        lines.extend(["### Brechas críticas", "", *_markdown_bullets(job.critical_gaps), ""])
        lines.extend(["### Otras brechas", "", *_markdown_bullets(job.other_gaps), ""])
        lines.extend(["### Recomendaciones", "", *_markdown_bullets(job.recommendations), ""])
        if job.penalties:
            lines.extend(["### Ajustes aplicados al score", ""])
            for penalty in job.penalties:
                lines.append(f"- -{penalty.points:.1f}: {penalty.reason}")
            lines.append("")
    return "\n".join(lines)


def _markdown_bullets(values: Iterable[str]) -> list[str]:
    items = [value for value in values if value]
    return [f"- {value}" for value in items] if items else ["- No disponible"]


def _render_result_message(result: CandidateExtractionResult, *, has_profile: bool) -> None:
    if result.success:
        st.success(
            "El perfil profesional fue extraído y validado correctamente.\n\n"
            "Revisa especialmente las inferencias, ambigüedades y conflictos antes de utilizar esta información "
            "en etapas posteriores."
        )
        if result.reused_from_session:
            st.info("Se reutilizó el análisis de esta sesión porque las fuentes no cambiaron.")
    else:
        st.error(result.user_message or "No fue posible extraer el perfil profesional estructurado.")
        if has_profile:
            st.warning(REPROCESS_FAILURE_MESSAGE)

    for warning in result.warnings:
        st.warning(warning)


def _render_identity(profile: CandidateProfessionalProfile) -> None:
    st.markdown("#### Identidad profesional")
    with st.container(border=True):
        st.markdown(f"**Identidad:** {profile.professional_identity}")
        st.markdown(f"**Seniority:** {profile.seniority}")
        total_years = (
            f"{profile.total_years_experience:g}"
            if profile.total_years_experience is not None
            else "No determinado"
        )
        st.markdown(f"**Total de años:** {total_years}")
        if profile.targetable_roles:
            st.markdown(f"**Roles respaldables:** {', '.join(profile.targetable_roles)}")
        st.markdown(f"**Resumen:** {profile.summary}")


def _render_industries(profile: CandidateProfessionalProfile) -> None:
    st.markdown("#### Industrias")
    if profile.industries:
        st.write(profile.industries)
    else:
        st.caption("No se detectaron industrias respaldadas con suficiente claridad.")


def _render_employment_history(employment_history: list[EmploymentEntry]) -> None:
    st.markdown("#### Experiencia laboral")
    if not employment_history:
        st.caption("No se extrajo historial laboral suficiente.")
        return

    for index, employment in enumerate(employment_history, start=1):
        with st.container(border=True):
            st.markdown(f"**{employment.role_title}**")
            st.caption(f"{employment.employer} | {_employment_period(employment)}")
            if employment.location:
                st.caption(employment.location)
            if employment.industries:
                st.markdown(f"**Industrias:** {', '.join(employment.industries)}")
            _render_evidence_group("Responsabilidades", employment.responsibilities, prefix=f"empleo-{index}-resp")
            _render_achievements(employment.achievements, prefix=f"empleo-{index}-ach")
            _render_skills(employment.technologies, heading="Tecnologías", prefix=f"empleo-{index}-tech")


def _render_skills(
    skills: list[CandidateSkill],
    *,
    heading: str = "Skills",
    prefix: str = "skills",
) -> None:
    st.markdown(f"#### {heading}")
    if not skills:
        st.caption("No se extrajeron elementos en esta sección.")
        return

    rows = []
    for skill in skills:
        rows.append(
            {
                "Skill": skill.name,
                "Categoría": skill.category,
                "Estado": _status_label(skill.evidence_status),
                "Confianza": f"{skill.confidence:.2f}",
                "Evidencia": _references_preview(skill.references),
            }
        )
    st.table(rows)
    for index, skill in enumerate(skills):
        _render_references(
            f"Ver evidencia - {skill.name}",
            skill.references,
            status=skill.evidence_status,
            confidence=skill.confidence,
            key=f"{prefix}-{index}",
        )


def _render_evidence_group(
    heading: str,
    items: list[EvidenceItem],
    *,
    prefix: str | None = None,
) -> None:
    st.markdown(f"#### {heading}")
    if not items:
        st.caption("No se extrajeron elementos en esta sección.")
        return

    for index, item in enumerate(items):
        st.markdown(f"- **{_status_label(item.status)}:** {item.statement}")
        if item.notes:
            st.caption(item.notes)
        _render_references(
            f"Ver evidencia - {heading} {index + 1}",
            item.references,
            status=item.status,
            confidence=item.confidence,
            key=f"{prefix or heading}-{index}",
        )


def _render_achievements(achievements: list[Achievement], *, prefix: str = "achievements") -> None:
    st.markdown("#### Logros")
    if not achievements:
        st.caption("No se extrajeron logros en esta sección.")
        return

    for index, achievement in enumerate(achievements):
        st.markdown(f"- **{_status_label(achievement.evidence_status)}:** {achievement.description}")
        if achievement.measurable_result:
            st.caption(f"Resultado medible: {achievement.measurable_result}")
        _render_references(
            f"Ver evidencia - Logro {index + 1}",
            achievement.references,
            status=achievement.evidence_status,
            confidence=None,
            key=f"{prefix}-{index}",
        )


def _render_human_review(
    profile: CandidateProfessionalProfile,
    result: CandidateExtractionResult | None,
) -> None:
    st.markdown("#### Revisión humana")
    with st.container(border=True):
        _render_text_list("Ambigüedades", profile.ambiguities)
        _render_text_list("Conflictos", profile.conflicts)
        _render_text_list("Información faltante", profile.missing_information)
        audit_warnings = [
            finding
            for finding in (result.evidence_audit_findings if result else [])
            if finding.startswith("warning:")
        ]
        _render_text_list("Advertencias de auditoría", audit_warnings)


def _render_technical_details(result: CandidateExtractionResult | None) -> None:
    if result is None:
        return
    with st.expander("Detalles de procesamiento"):
        st.caption(f"Modelo: {result.model_used or 'No disponible'}")
        st.caption(f"Tokens de entrada: {_token_label(result.input_tokens)}")
        st.caption(f"Tokens de salida: {_token_label(result.output_tokens)}")
        st.caption(f"Tokens totales: {_token_label(result.total_tokens)}")
        st.caption(f"Latencia: {_token_label(result.latency_ms)} ms")
        st.caption(f"Request ID: {result.request_id or 'No disponible'}")
        st.caption(f"Reutilizado en sesión: {'Sí' if result.reused_from_session else 'No'}")
        if result.evidence_audit_findings:
            st.caption("Hallazgos de auditoría:")
            for finding in result.evidence_audit_findings:
                st.caption(finding)


def _render_references(
    label: str,
    references: list[EvidenceReference],
    *,
    status: str,
    confidence: float | None,
    key: str,
) -> None:
    if not references:
        return
    with st.expander(label):
        st.caption(f"Estado: {_status_label(status)}")
        if confidence is not None:
            st.caption(f"Confianza: {confidence:.2f}")
        for reference in references:
            st.markdown(f"**Sección fuente:** {reference.source_section}")
            st.caption(reference.source_excerpt)


def _render_text_list(heading: str, values: Iterable[str]) -> None:
    values = list(values)
    st.markdown(f"**{heading}**")
    if not values:
        st.caption("Sin elementos.")
        return
    for value in values:
        st.markdown(f"- {value}")


def _references_preview(references: list[EvidenceReference]) -> str:
    if not references:
        return "Sin referencia"
    return references[0].source_excerpt[:120]


def _employment_period(employment: EmploymentEntry) -> str:
    if not employment.start_date and not employment.end_date:
        return "Periodo no especificado"
    end_date = "Actual" if employment.is_current else employment.end_date
    return f"{employment.start_date or 'Sin inicio'} - {end_date or 'Sin fin'}"


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(str(status), str(status))


def _token_label(value: int | None) -> str:
    return str(value) if value is not None else "No disponible"


def _current_extraction_result() -> CandidateExtractionResult | None:
    raw = st.session_state.get(SessionKeys.CANDIDATE_EXTRACTION_RESULT)
    if not raw:
        return None
    try:
        return CandidateExtractionResult.model_validate(raw)
    except ValueError:
        return None


def _current_profile() -> CandidateProfessionalProfile | None:
    raw = st.session_state.get(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE)
    if not raw:
        return None
    try:
        return CandidateProfessionalProfile.model_validate(raw)
    except ValueError:
        return None


def _current_job_analysis_result() -> JobAnalysisResult | None:
    raw = st.session_state.get(SessionKeys.JOB_ANALYSIS_RESULT)
    if not raw:
        return None
    try:
        return JobAnalysisResult.model_validate(raw)
    except ValueError:
        return None


def _current_linkedin_generation_result() -> LinkedInProfileGenerationResult | None:
    raw = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT)
    if not raw:
        return None
    try:
        return LinkedInProfileGenerationResult.model_validate(raw)
    except ValueError:
        return None


def _current_linkedin_profile_output() -> LinkedInProfileOutput | None:
    raw = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_OUTPUT)
    if not raw:
        return None
    try:
        return LinkedInProfileOutput.model_validate(raw)
    except ValueError:
        return None


def _current_compatibility_result() -> CompatibilityAnalysisResult | None:
    raw = st.session_state.get(SessionKeys.COMPATIBILITY_ANALYSIS_RESULT)
    if not raw:
        return None
    try:
        return CompatibilityAnalysisResult.model_validate(raw)
    except ValueError:
        return None


def _current_compatibility_report() -> CompatibilityReport | None:
    raw = st.session_state.get(SessionKeys.COMPATIBILITY_REPORT)
    if not raw:
        return None
    try:
        return CompatibilityReport.model_validate(raw)
    except ValueError:
        return None


def _current_final_audit_report() -> AuditReport | None:
    raw = st.session_state.get(SessionKeys.FINAL_AUDIT_REPORT)
    if not raw:
        return None
    try:
        return AuditReport.model_validate(raw)
    except ValueError:
        return None


def _current_final_package_build_result() -> FinalPackageBuildResult | None:
    raw = st.session_state.get(SessionKeys.FINAL_PACKAGE_BUILD_RESULT)
    if not raw:
        return None
    try:
        return FinalPackageBuildResult.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cv_generation_result(job_index: int) -> TargetedCVGenerationResult | None:
    raw = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_GENERATION_RESULTS, job_index)
    if not raw:
        return None
    try:
        return TargetedCVGenerationResult.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cv(job_index: int) -> TargetedCV | None:
    raw = _targeted_cv_dict_get(SessionKeys.TARGETED_CVS, job_index)
    if not raw:
        return None
    try:
        return TargetedCV.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cvs() -> dict[int, TargetedCV]:
    return _targeted_cv_model_dict(SessionKeys.TARGETED_CVS, TargetedCV)


def _current_targeted_cv_audit(job_index: int) -> TargetedCVAuditResult | None:
    raw = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_AUDITS, job_index)
    if not raw:
        return None
    try:
        return TargetedCVAuditResult.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cv_audits() -> dict[int, TargetedCVAuditResult]:
    return _targeted_cv_model_dict(SessionKeys.TARGETED_CV_AUDITS, TargetedCVAuditResult)


def _current_targeted_cv_ats_audit(job_index: int) -> TargetedCVATSAudit | None:
    raw = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_ATS_AUDITS, job_index)
    if not raw:
        return None
    try:
        return TargetedCVATSAudit.model_validate(raw)
    except ValueError:
        return None


def _current_targeted_cv_ats_audits() -> dict[int, TargetedCVATSAudit]:
    return _targeted_cv_model_dict(SessionKeys.TARGETED_CV_ATS_AUDITS, TargetedCVATSAudit)


def _current_targeted_cv_edit_validation(job_index: int) -> TargetedCVEditableValidationResult | None:
    raw = _targeted_cv_dict_get(SessionKeys.TARGETED_CV_EDIT_VALIDATIONS, job_index)
    if not raw:
        return None
    try:
        return TargetedCVEditableValidationResult.model_validate(raw)
    except ValueError:
        return None


def _targeted_cv_model_dict(session_key: str, model_class) -> dict[int, object]:
    output = {}
    raw = st.session_state.get(session_key) or {}
    if not isinstance(raw, dict):
        return output
    for key, value in raw.items():
        if not value:
            continue
        try:
            output[int(key)] = model_class.model_validate(value)
        except (TypeError, ValueError):
            continue
    return output


def _targeted_cv_dict_get(session_key: str, job_index: int) -> object | None:
    raw = st.session_state.get(session_key) or {}
    if not isinstance(raw, dict):
        return None
    return raw.get(str(job_index)) or raw.get(job_index)


def _targeted_cv_dict_set(session_key: str, job_index: int, value: object | None) -> None:
    raw = st.session_state.get(session_key)
    if not isinstance(raw, dict):
        raw = {}
    if value is None:
        raw.pop(str(job_index), None)
        raw.pop(job_index, None)
    else:
        raw[str(job_index)] = value
    st.session_state[session_key] = raw


def _format_targeted_cv_bytes(session_key: str, job_index: int) -> str:
    data = _targeted_cv_dict_get(session_key, job_index) or b""
    return f"{len(data) / 1024:.1f} KB" if data else "Pendiente"


def _current_output_language() -> str:
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if raw_input:
        try:
            language = CandidateInput.model_validate(raw_input).output_language
            return language.value if hasattr(language, "value") else str(language)
        except ValueError:
            pass
    fallback = st.session_state.get(SessionKeys.OUTPUT_LANGUAGE, DEFAULT_OUTPUT_LANGUAGE)
    return fallback.value if hasattr(fallback, "value") else str(fallback)


def _current_market_analysis() -> TargetMarketAnalysis | None:
    raw = st.session_state.get(SessionKeys.TARGET_MARKET_ANALYSIS)
    if not raw:
        return None
    try:
        return TargetMarketAnalysis.model_validate(raw)
    except ValueError:
        return None


def _band_label(value: object) -> str:
    key = str(getattr(value, "value", value))
    return COMPATIBILITY_BAND_LABELS_ES.get(key, key)


def _coverage_label(value: object) -> str:
    key = str(getattr(value, "value", value))
    labels = {
        RequirementCoverage.FULL.value: "Completa",
        RequirementCoverage.PARTIAL.value: "Parcial",
        RequirementCoverage.INDIRECT.value: "Indirecta",
        RequirementCoverage.MISSING.value: "Faltante",
        RequirementCoverage.CONFLICT.value: "Conflicto",
        RequirementCoverage.NOT_APPLICABLE.value: "No aplicable",
    }
    return labels.get(key, key)
