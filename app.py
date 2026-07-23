"""Streamlit entrypoint for Astrogato Vector."""

from dotenv import load_dotenv
import streamlit as st

from components.branding import render_header, render_page_styles
from components.input_form import render_input_form
from components.notices import render_notice
from components.openai_diagnostic import render_openai_diagnostic_sidebar
from components.result_views import render_results
from utils.session import consume_clear_request, initialize_session_state


def main() -> None:
    """Render the initial pilot interface."""
    load_dotenv()

    st.set_page_config(
        page_title="Astrogato Vector",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    initialize_session_state()
    consume_clear_request()
    render_openai_diagnostic_sidebar()
    render_page_styles()
    render_header()
    render_notice()
    render_input_form()
    render_results()


if __name__ == "__main__":
    main()
