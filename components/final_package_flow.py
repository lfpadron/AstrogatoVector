"""Streamlit orchestration for the final deliverable package."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from exporters.final_package_exporter import FinalPackageExporter
from schemas.audit_models import AuditReport
from schemas.banner_models import BannerRenderInput, BannerRenderResult
from schemas.compatibility_models import CompatibilityReport
from schemas.deliverable_models import FinalPackageBuildResult
from schemas.enums import OutputLanguage
from schemas.evidence_models import CandidateProfessionalProfile
from schemas.input_models import CandidateInput
from schemas.market_models import TargetMarketAnalysis
from schemas.profile_models import LinkedInProfileOutput
from services.banner_service import build_banner_render_fingerprint
from services.export_audit_service import ExportAuditService
from services.final_package_service import (
    FINAL_PACKAGE_MISSING_AUDIT_MESSAGE,
    FINAL_PACKAGE_SUCCESS_MESSAGE,
    FinalPackageService,
)
from utils.constants import DEFAULT_OUTPUT_LANGUAGE
from utils.session import SessionKeys, clear_final_package_state

FINAL_PACKAGE_EXPORT_FAILURE_MESSAGE = (
    "El paquete fue consolidado, pero los archivos generados no superaron la auditoría local de exportación."
)
FINAL_PACKAGE_REUSE_MESSAGE = "Se reutilizó el paquete final porque el contenido editable y los resultados no cambiaron."


def build_final_package_from_session(
    *,
    force: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> FinalPackageBuildResult:
    """Build, export and store final package artifacts in Streamlit session."""
    profile = _current_candidate_profile()
    market = _current_market_analysis()
    linkedin_output = _current_linkedin_profile_output()
    compatibility = _current_compatibility_report()
    audit = _current_final_audit_report()
    output_language = _current_output_language()
    if profile is None or market is None or linkedin_output is None or compatibility is None:
        result = FinalPackageBuildResult(
            success=False,
            validation_passed=False,
            findings=["error: faltan etapas previas validadas."],
            error_category="missing_previous_stages",
            user_message="Para generar el paquete final se necesitan resultados validados de perfil, mercado, LinkedIn y compatibilidad.",
        )
        _store_build_result(result, clear_bytes=True)
        return result
    if audit is None or not audit.success:
        result = FinalPackageBuildResult(
            success=False,
            validation_passed=False,
            findings=["error: auditoría presente."],
            error_category="missing_final_audit",
            user_message=FINAL_PACKAGE_MISSING_AUDIT_MESSAGE,
        )
        _store_build_result(result, clear_bytes=True)
        return result

    edit_state = _current_edit_state()
    banner_bytes, banner_fingerprint = _current_banner_bytes_and_fingerprint(edit_state)
    package_result = FinalPackageService().build_package(
        profile,
        market,
        linkedin_output,
        compatibility,
        audit,
        output_language,
        edit_state=edit_state,
        banner_available=bool(banner_bytes),
        banner_fingerprint=banner_fingerprint,
    )
    existing_fingerprint = st.session_state.get(SessionKeys.FINAL_PACKAGE_FINGERPRINT)
    if (
        package_result.success
        and not force
        and existing_fingerprint
        and existing_fingerprint == package_result.package_fingerprint
        and _stored_exports_available()
    ):
        reused = package_result.model_copy(update={"warnings": [*package_result.warnings, FINAL_PACKAGE_REUSE_MESSAGE]})
        _store_build_result(reused, clear_bytes=False)
        return reused

    if not package_result.success or package_result.package is None:
        _store_build_result(package_result, clear_bytes=True)
        return package_result

    if status_callback:
        status_callback("Generando archivos del paquete...")
    exporter = FinalPackageExporter()
    markdown_bytes = exporter.export_markdown(package_result.package)
    html_bytes = exporter.export_html(package_result.package, banner_image_bytes=banner_bytes)
    docx_bytes = exporter.export_docx(package_result.package, banner_image_bytes=banner_bytes)
    pdf_bytes = exporter.export_pdf(package_result.package, banner_image_bytes=banner_bytes)
    zip_bytes = exporter.export_zip(package_result.package, banner_image_bytes=banner_bytes)
    exports = {
        "markdown": markdown_bytes,
        "html": html_bytes,
        "docx": docx_bytes,
        "pdf": pdf_bytes,
        "zip": zip_bytes,
    }
    if status_callback:
        status_callback("Auditando archivos generados...")
    export_audit = ExportAuditService().audit_all(exports)
    if not export_audit.passed:
        failed = package_result.model_copy(
            update={
                "success": False,
                "validation_passed": False,
                "findings": [*package_result.findings, *export_audit.findings],
                "warnings": [*package_result.warnings, *export_audit.warnings],
                "error_category": "export_audit_failed",
                "user_message": FINAL_PACKAGE_EXPORT_FAILURE_MESSAGE,
            }
        )
        _store_build_result(failed, clear_bytes=True)
        return failed

    _store_build_result(package_result, clear_bytes=True)
    st.session_state[SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES] = markdown_bytes
    st.session_state[SessionKeys.FINAL_PACKAGE_HTML_BYTES] = html_bytes
    st.session_state[SessionKeys.FINAL_PACKAGE_DOCX_BYTES] = docx_bytes
    st.session_state[SessionKeys.FINAL_PACKAGE_PDF_BYTES] = pdf_bytes
    st.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES] = zip_bytes
    st.session_state[SessionKeys.FINAL_PACKAGE_FINGERPRINT] = package_result.package_fingerprint
    st.session_state[SessionKeys.FINAL_PACKAGE_LAST_BUILD] = datetime.now().isoformat(timespec="seconds")
    return package_result


def _store_build_result(result: FinalPackageBuildResult, *, clear_bytes: bool) -> None:
    st.session_state[SessionKeys.FINAL_PACKAGE_BUILD_RESULT] = result.model_dump()
    if clear_bytes:
        st.session_state[SessionKeys.FINAL_PACKAGE_FINGERPRINT] = None
        st.session_state[SessionKeys.FINAL_PACKAGE_MARKDOWN_BYTES] = None
        st.session_state[SessionKeys.FINAL_PACKAGE_HTML_BYTES] = None
        st.session_state[SessionKeys.FINAL_PACKAGE_DOCX_BYTES] = None
        st.session_state[SessionKeys.FINAL_PACKAGE_PDF_BYTES] = None
        st.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES] = None
        st.session_state[SessionKeys.FINAL_PACKAGE_LAST_BUILD] = None


def invalidate_final_package_exports() -> None:
    """Clear package exports when editable content changes."""
    clear_final_package_state()


def _current_candidate_profile() -> CandidateProfessionalProfile | None:
    return _model_from_session(SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE, CandidateProfessionalProfile)


def _current_market_analysis() -> TargetMarketAnalysis | None:
    return _model_from_session(SessionKeys.TARGET_MARKET_ANALYSIS, TargetMarketAnalysis)


def _current_linkedin_profile_output() -> LinkedInProfileOutput | None:
    return _model_from_session(SessionKeys.LINKEDIN_PROFILE_OUTPUT, LinkedInProfileOutput)


def _current_compatibility_report() -> CompatibilityReport | None:
    return _model_from_session(SessionKeys.COMPATIBILITY_REPORT, CompatibilityReport)


def _current_final_audit_report() -> AuditReport | None:
    return _model_from_session(SessionKeys.FINAL_AUDIT_REPORT, AuditReport)


def _current_output_language() -> OutputLanguage | str:
    raw_input = st.session_state.get(SessionKeys.VALIDATED_INPUT)
    if raw_input:
        try:
            return CandidateInput.model_validate(raw_input).output_language
        except ValueError:
            pass
    return st.session_state.get(SessionKeys.OUTPUT_LANGUAGE, DEFAULT_OUTPUT_LANGUAGE)


def _current_edit_state() -> dict[str, Any] | None:
    edit_state = st.session_state.get(SessionKeys.LINKEDIN_PROFILE_EDIT_STATE)
    return edit_state if isinstance(edit_state, dict) else None


def _current_banner_bytes_and_fingerprint(edit_state: dict[str, Any] | None) -> tuple[bytes | None, str | None]:
    stored_bytes = st.session_state.get(SessionKeys.BANNER_IMAGE_BYTES)
    stored_result = _model_from_session(SessionKeys.BANNER_RENDER_RESULT, BannerRenderResult)
    if not edit_state or not stored_bytes or not stored_result or not stored_result.success:
        return None, None
    current_fingerprint = _current_banner_fingerprint(edit_state)
    if not current_fingerprint or stored_result.fingerprint != current_fingerprint:
        return None, None
    return stored_bytes, current_fingerprint


def _current_banner_fingerprint(edit_state: dict[str, Any]) -> str | None:
    banner = edit_state.get("banner") if isinstance(edit_state.get("banner"), dict) else {}
    payload = {
        "primary_line": banner.get("primary_line", ""),
        "specialty_line": banner.get("specialty_line", ""),
        "supporting_line": banner.get("supporting_line") or None,
        "visual_concept": banner.get("visual_concept"),
        "template_id": banner.get("recommended_template", "professional_light"),
        "output_language": _current_output_language(),
    }
    try:
        return build_banner_render_fingerprint(BannerRenderInput.model_validate(payload))
    except ValueError:
        return None


def _stored_exports_available() -> bool:
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


def _model_from_session(key: str, model_class):
    raw = st.session_state.get(key)
    if not raw:
        return None
    try:
        return model_class.model_validate(raw)
    except ValueError:
        return None
