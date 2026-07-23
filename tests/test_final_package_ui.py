from __future__ import annotations

from streamlit.testing.v1 import AppTest

from schemas.banner_models import BannerRenderResult
from schemas.examples import (
    build_example_audit_report,
    build_example_compatibility_report,
    build_example_linkedin_profile,
    build_example_market_analysis,
    build_example_professional_profile,
)
from services.banner_service import build_banner_render_fingerprint
from schemas.banner_models import BannerRenderInput
from tests.final_package_helpers import fake_banner_bytes
from utils.session import SessionKeys


def test_final_package_ui_generates_downloads_without_openai(monkeypatch):
    def forbidden_openai(*args, **kwargs):
        raise AssertionError("Final package export must not call OpenAI.")

    monkeypatch.setattr("components.result_views.run_linkedin_profile_generation_from_session", forbidden_openai)
    at = _app_with_state()
    at.run(timeout=15)
    next(button for button in at.button if button.label == "Generar paquete final").click()
    at.run(timeout=30)

    labels = _download_labels(at)
    assert "Descargar Markdown" in labels
    assert "Descargar HTML" in labels
    assert "Descargar DOCX" in labels
    assert "Descargar PDF" in labels
    assert "Descargar paquete completo ZIP" in labels
    assert at.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES].startswith(b"PK")
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in _page_text(at)
    assert "OPENAI_API_KEY" not in _page_text(at)


def test_final_package_ui_blocks_when_audit_missing():
    at = _app_with_state(audit_payload=None)
    at.run(timeout=15)

    assert "Para generar el paquete final es necesario completar primero la auditoría integral." in _page_text(at)
    assert "Descargar paquete completo ZIP" not in _download_labels(at)


def test_final_package_ui_allows_package_without_banner_and_warns():
    at = _app_with_state(include_banner=False)
    at.run(timeout=15)
    next(button for button in at.button if button.label == "Generar paquete final").click()
    at.run(timeout=30)

    assert at.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES]
    assert "Banner PNG not included." in _page_text(at)
    assert "Descargar banner PNG" not in _download_labels(at)


def test_final_package_ui_reuses_fingerprint_and_blocks_sensitive_edit():
    at = _app_with_state()
    at.run(timeout=15)
    next(button for button in at.button if button.label == "Generar paquete final").click()
    at.run(timeout=30)
    first_fingerprint = at.session_state[SessionKeys.FINAL_PACKAGE_FINGERPRINT]
    at.run(timeout=15)
    next(button for button in at.button if button.label == "Regenerar paquete final").click()
    at.run(timeout=30)
    assert at.session_state[SessionKeys.FINAL_PACKAGE_FINGERPRINT] == first_fingerprint
    assert "Se reutilizó el paquete final" in _page_text(at)

    sensitive = _app_with_state(edit_headline="Project Manager RFC ABCD010101XYZ")
    sensitive.run(timeout=15)
    next(button for button in sensitive.button if button.label == "Generar paquete final").click()
    sensitive.run(timeout=30)
    assert sensitive.session_state[SessionKeys.FINAL_PACKAGE_ZIP_BYTES] is None
    assert "dato sensible" in _page_text(sensitive)


def _app_with_state(include_banner: bool = True, audit_payload="default", edit_headline: str | None = None) -> AppTest:
    linkedin = build_example_linkedin_profile()
    edit_state = {
        "edited": bool(edit_headline),
        "banner": {
            "primary_line": linkedin.banner.primary_line,
            "specialty_line": linkedin.banner.specialty_line,
            "supporting_line": linkedin.banner.supporting_line or "",
            "visual_concept": linkedin.banner.visual_concept,
            "recommended_template": linkedin.banner.recommended_template,
        },
        "headline": edit_headline or linkedin.headline.text,
        "about": linkedin.about.text,
        "experience": [
            {
                "employer": item.employer,
                "source_role_title": item.source_role_title,
                "suggested_role_title": item.suggested_role_title,
                "rewritten_text": item.rewritten_text,
                "included_keywords": item.included_keywords,
            }
            for item in linkedin.experience
        ],
        "selected_skills": [skill.name for skill in linkedin.prioritized_skills],
        "selected_keywords": [keyword.keyword for keyword in linkedin.ats_keywords],
    }
    banner_payload = BannerRenderInput(
        primary_line=linkedin.banner.primary_line,
        specialty_line=linkedin.banner.specialty_line,
        supporting_line=linkedin.banner.supporting_line,
        visual_concept=linkedin.banner.visual_concept,
        template_id=linkedin.banner.recommended_template,
        output_language="es",
    )
    banner_fingerprint = build_banner_render_fingerprint(banner_payload)
    banner_result = BannerRenderResult(
        success=True,
        image_bytes=fake_banner_bytes(),
        template_id=linkedin.banner.recommended_template,
        filename="astrogato-vector-linkedin-banner.png",
        fingerprint=banner_fingerprint,
        contrast_passed=True,
        overflow_passed=True,
        safe_zone_passed=True,
    )
    return AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "profile_payload": build_example_professional_profile().model_dump(),
            "market_payload": build_example_market_analysis().model_dump(),
            "linkedin_payload": linkedin.model_dump(),
            "compatibility_payload": build_example_compatibility_report().model_dump(),
            "audit_payload": build_example_audit_report().model_dump() if audit_payload == "default" else audit_payload,
            "edit_state": edit_state,
            "banner_result": banner_result.model_dump() if include_banner else None,
            "banner_bytes": fake_banner_bytes() if include_banner else None,
        },
    )


def _render_results_with_state(
    profile_payload=None,
    market_payload=None,
    linkedin_payload=None,
    compatibility_payload=None,
    audit_payload=None,
    edit_state=None,
    banner_result=None,
    banner_bytes=None,
):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_final_package_ui_test_seeded"):
        st.session_state["_final_package_ui_test_seeded"] = True
        st.session_state[SessionKeys.CANDIDATE_PROFESSIONAL_PROFILE] = profile_payload
        st.session_state[SessionKeys.TARGET_MARKET_ANALYSIS] = market_payload
        st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = linkedin_payload
        st.session_state[SessionKeys.COMPATIBILITY_REPORT] = compatibility_payload
        st.session_state[SessionKeys.FINAL_AUDIT_REPORT] = audit_payload
        st.session_state[SessionKeys.LINKEDIN_PROFILE_EDIT_STATE] = edit_state
        if banner_result is not None:
            st.session_state[SessionKeys.BANNER_RENDER_RESULT] = banner_result
            st.session_state[SessionKeys.BANNER_IMAGE_BYTES] = banner_bytes
    render_results()


def _download_labels(at: AppTest) -> list[str]:
    return [button.label for button in getattr(at, "download_button", [])]


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    values.extend(str(table.value) for table in at.table)
    return "\n".join(values)
