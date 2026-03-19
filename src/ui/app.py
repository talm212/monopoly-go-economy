"""Main entry point for the Monopoly Go Economy Simulator dashboard."""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Monopoly Go Economy Simulator",
    page_icon="\U0001f3b2",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar branding
st.sidebar.title("Economy Simulator")
st.sidebar.markdown("---")
st.sidebar.markdown("Each feature is a single page with tabbed workflow.")
st.sidebar.markdown("Use the navigation above to switch features.")

# Home page content
st.title("Monopoly Go Economy Simulator")
st.markdown("Economy simulation platform for the Monopoly Go game.")
st.markdown("### Features")
st.markdown("- **Coin Flip** — simulate coin flip mechanics with configurable parameters")
st.markdown("- **AI Insights** — LLM-powered analysis, chat, and config optimization")
st.markdown("- **History** — browse, compare, and manage past simulation runs")
st.markdown("### Getting Started")
st.markdown("Select **Coin Flip** from the sidebar to upload data, run simulations, and view results — all in one page.")
