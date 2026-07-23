from __future__ import annotations

from streamlit.testing.v1 import AppTest

from utils.session import SessionKeys


def test_banner_session_defaults_are_transient_empty_values():
    from utils.session import build_session_defaults

    defaults = build_session_defaults()

    assert defaults[SessionKeys.BANNER_RENDER_FINGERPRINT] is None
    assert defaults[SessionKeys.BANNER_RENDER_RESULT] is None
    assert defaults[SessionKeys.BANNER_IMAGE_BYTES] is None
    assert defaults[SessionKeys.BANNER_LAST_RENDER] is None


def test_clear_linkedin_profile_generation_state_clears_banner_render_state():
    at = AppTest.from_function(_render_and_clear_banner_state)
    at.run(timeout=10)

    assert at.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] is None
    assert at.session_state[SessionKeys.BANNER_RENDER_RESULT] is None
    assert at.session_state[SessionKeys.BANNER_IMAGE_BYTES] is None
    assert at.session_state[SessionKeys.BANNER_LAST_RENDER] is None


def _render_and_clear_banner_state():
    import streamlit as st

    from utils.session import SessionKeys, clear_linkedin_profile_generation_state, initialize_session_state

    initialize_session_state()
    st.session_state[SessionKeys.BANNER_RENDER_FINGERPRINT] = "fingerprint"
    st.session_state[SessionKeys.BANNER_RENDER_RESULT] = {"success": True}
    st.session_state[SessionKeys.BANNER_IMAGE_BYTES] = b"png"
    st.session_state[SessionKeys.BANNER_LAST_RENDER] = "2026-07-22T12:00:00"
    clear_linkedin_profile_generation_state()
