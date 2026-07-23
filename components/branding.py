"""Branding and visual presentation for the Streamlit interface."""

import streamlit as st

from utils.constants import PRODUCT_DESCRIPTION, PRODUCT_NAME, PRODUCT_SUBTITLE


def render_page_styles() -> None:
    """Inject the minimal CSS needed for the pilot interface."""
    st.markdown(
        """
        <style>
        :root {
            --av-primary: #12355b;
            --av-secondary: #2f6f9f;
            --av-accent: #f28c28;
            --av-bg: #f7f9fc;
            --av-text: #1d2733;
            --av-muted: #667085;
            --av-card-border: #dde5ef;
        }

        .stApp {
            background: var(--av-bg);
            color: var(--av-text);
        }

        #MainMenu, footer, header {
            visibility: hidden;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1180px;
        }

        .av-header {
            border-left: 5px solid var(--av-accent);
            padding: 0.4rem 0 0.4rem 1.1rem;
            margin-bottom: 1.2rem;
        }

        .av-kicker {
            color: var(--av-secondary);
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0;
            margin-bottom: 0.25rem;
        }

        .av-title {
            color: var(--av-primary);
            font-size: 2.55rem;
            font-weight: 800;
            line-height: 1.08;
            margin: 0;
        }

        .av-subtitle {
            color: var(--av-muted);
            font-size: 1.08rem;
            margin-top: 0.45rem;
            max-width: 820px;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--av-card-border);
            border-radius: 8px;
            background: #ffffff;
        }

        .av-section-title {
            color: var(--av-primary);
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .av-helper {
            color: var(--av-muted);
            font-size: 0.92rem;
            margin-top: -0.2rem;
        }

        .av-notice {
            background: #fff8ef;
            border: 1px solid #ffd7a6;
            border-left: 5px solid var(--av-accent);
            border-radius: 8px;
            color: #49321b;
            padding: 1rem 1.1rem;
            margin: 1rem 0 1.25rem;
        }

        .av-notice strong {
            color: #2f2012;
        }

        .stButton > button[kind="primary"] {
            background: var(--av-primary);
            border-color: var(--av-primary);
        }

        .stButton > button[kind="primary"]:hover {
            background: #0e2b4b;
            border-color: #0e2b4b;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 0.45rem 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Render the product name, subtitle and short description."""
    st.markdown(
        f"""
        <section class="av-header">
            <div class="av-kicker">✦ {PRODUCT_NAME}</div>
            <h1 class="av-title">{PRODUCT_NAME}</h1>
            <div class="av-subtitle"><strong>{PRODUCT_SUBTITLE}</strong></div>
            <p class="av-subtitle">{PRODUCT_DESCRIPTION}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
