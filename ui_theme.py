import streamlit as st


def apply_suite_theme():
    st.markdown(
        """
        <style>
        .main {
            background: linear-gradient(180deg, #0b1020 0%, #111827 100%);
            color: #f9fafb;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        h1, h2, h3 {
            color: #f9fafb;
            letter-spacing: -0.02em;
        }

        p, li, .stMarkdown, label {
            color: #d1d5db;
        }

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 18px;
        }

        div[data-testid="stMetricValue"] {
            color: #ffffff;
        }

        div[data-testid="stMetricLabel"] {
            color: #cbd5e1;
        }

        .suite-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 18px 20px;
            margin-bottom: 16px;
        }

        .suite-caption {
            color: #94a3b8;
            font-size: 0.95rem;
        }

        .suite-tag {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 999px;
            background: rgba(96,165,250,0.15);
            color: #bfdbfe;
            font-size: 0.8rem;
            margin-right: 0.4rem;
            margin-bottom: 0.4rem;
        }

        .suite-divider {
            margin-top: 0.75rem;
            margin-bottom: 1.25rem;
            border-top: 1px solid rgba(255,255,255,0.08);
        }

        .stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.12);
            background: #2563eb;
            color: white;
            font-weight: 600;
        }

        .stButton > button:hover {
            background: #1d4ed8;
            color: white;
            border-color: rgba(255,255,255,0.16);
        }

        .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 12px;
        }

        footer {
            visibility: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, tags=None):
    tags = tags or []

    st.markdown(f"# {title}")
    st.markdown(f"<div class='suite-caption'>{subtitle}</div>", unsafe_allow_html=True)

    if tags:
        tags_html = "".join([f"<span class='suite-tag'>{tag}</span>" for tag in tags])
        st.markdown(tags_html, unsafe_allow_html=True)

    st.markdown("<div class='suite-divider'></div>", unsafe_allow_html=True)