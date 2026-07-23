"""Notice and consent components."""

import streamlit as st

from utils.constants import CONSENT_TEXT, PILOT_NOTICE
from utils.session import SessionKeys


def render_notice() -> None:
    """Render the complete pilot notice and mandatory consent control."""
    st.markdown(
        f"""
        <div class="av-notice">
            <strong>Aviso importante sobre el uso del sistema</strong><br>
            {PILOT_NOTICE}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.checkbox(CONSENT_TEXT, key=SessionKeys.CONSENT_ACCEPTED)
