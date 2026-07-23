from __future__ import annotations

from streamlit.testing.v1 import AppTest

from schemas.profile_generation_models import LinkedInProfileGenerationResult
from tests.linkedin_profile_helpers import build_linkedin_output
from utils.session import SessionKeys


def test_banner_ui_shows_controls_without_png_before_generation():
    at = _app_with_linkedin_output()
    at.run(timeout=10)

    assert any(selectbox.label == "Estilo visual" for selectbox in at.selectbox)
    style = next(selectbox for selectbox in at.selectbox if selectbox.label == "Estilo visual")
    assert style.value in {"professional_light", "Profesional claro"}
    assert "Generar banner PNG" in _button_labels(at)
    assert at.session_state[SessionKeys.BANNER_IMAGE_BYTES] is None
    assert "Descargar banner PNG" not in _download_labels(at)
    assert "Descargar perfil LinkedIn optimizado (.md)" in _download_labels(at)


def test_banner_ui_generates_preview_download_and_fingerprint_without_openai(monkeypatch):
    def forbidden_openai_call(*args, **kwargs):
        raise AssertionError("Banner generation must not call OpenAI.")

    monkeypatch.setattr("components.result_views.run_linkedin_profile_generation_from_session", forbidden_openai_call)
    at = _app_with_linkedin_output()
    at.run(timeout=10)

    next(button for button in at.button if button.label == "Generar banner PNG").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.BANNER_IMAGE_BYTES].startswith(b"\x89PNG\r\n\x1a\n")
    assert at.session_state[SessionKeys.BANNER_RENDER_RESULT]["success"] is True
    assert at.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT]
    assert at.session_state[SessionKeys.BANNER_LAST_RENDER]
    assert "Validación del banner" in _page_text(at)
    assert "Descargar banner PNG" in _download_labels(at)
    assert "Descargas" in _page_text(at)
    assert "unit-test-secret" not in _page_text(at)
    assert "CV_COMPLETO_NO_DEBE_MOSTRARSE" not in _page_text(at)


def test_banner_ui_regenerates_when_template_changes():
    at = _app_with_linkedin_output()
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Generar banner PNG").click()
    at.run(timeout=10)
    first_fingerprint = at.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT]
    first_bytes = at.session_state[SessionKeys.BANNER_IMAGE_BYTES]

    style = next(selectbox for selectbox in at.selectbox if selectbox.label == "Estilo visual")
    _set_selectbox_value(style, "professional_dark")
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Regenerar banner PNG").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] != first_fingerprint
    assert at.session_state[SessionKeys.BANNER_IMAGE_BYTES] != first_bytes


def test_banner_ui_blocks_too_long_text_and_hides_download():
    at = _app_with_linkedin_output()
    at.run(timeout=10)
    next(area for area in at.text_area if area.label == "Línea principal").set_value("X" * 121)
    at.run(timeout=10)
    next(button for button in at.button if button.label == "Generar banner PNG").click()
    at.run(timeout=10)

    assert at.session_state[SessionKeys.BANNER_IMAGE_BYTES] is None
    assert at.session_state[SessionKeys.BANNER_RENDER_RESULT]["success"] is False
    assert "demasiado extenso" in _page_text(at)
    assert "Descargar banner PNG" not in _download_labels(at)


def _app_with_linkedin_output() -> AppTest:
    result = LinkedInProfileGenerationResult(
        success=True,
        profile_output=build_linkedin_output(),
        model_used="quality-model",
        audit_passed=True,
        prompt_version="1.0",
    )
    return AppTest.from_function(
        _render_results_with_state,
        kwargs={
            "generation_result_payload": result.model_dump(),
            "profile_output_payload": build_linkedin_output().model_dump(),
        },
    )


def _render_results_with_state(generation_result_payload=None, profile_output_payload=None):
    import streamlit as st

    from components.result_views import render_results
    from utils.session import SessionKeys, initialize_session_state

    initialize_session_state()
    if not st.session_state.get("_banner_ui_test_seeded"):
        st.session_state["_banner_ui_test_seeded"] = True
        if generation_result_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_GENERATION_RESULT] = generation_result_payload
        if profile_output_payload is not None:
            st.session_state[SessionKeys.LINKEDIN_PROFILE_OUTPUT] = profile_output_payload
    render_results()


def _set_selectbox_value(selectbox, value: str) -> None:
    if hasattr(selectbox, "select"):
        selectbox.select(value)
    else:
        selectbox.set_value(value)


def _button_labels(at: AppTest) -> list[str]:
    return [button.label for button in at.button]


def _download_labels(at: AppTest) -> list[str]:
    return [button.label for button in getattr(at, "download_button", [])]


def _page_text(at: AppTest) -> str:
    values = []
    for collection in (at.markdown, at.caption, at.success, at.warning, at.error, at.info):
        values.extend(str(item.value) for item in collection)
    return "\n".join(values)
