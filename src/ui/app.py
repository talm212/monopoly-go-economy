"""Main entry point for the Monopoly Go Economy Simulator dashboard."""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Monopoly Go Economy Simulator",
    page_icon="\U0001f3b2",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar branding — page links are auto-generated from src/ui/pages/
st.sidebar.title("Economy Simulator")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "Use the navigation above to switch between pages."
)

# Home page content
st.title("Monopoly Go Economy Simulator")
st.markdown("Welcome to the economy simulation platform. Use the sidebar to navigate.")
st.markdown("### Quick Start")
st.markdown("1. **Upload & Configure** — upload player data and config CSVs")
st.markdown("2. **Run Simulation** — execute the coin-flip simulation")
st.markdown("3. **Results** — view KPIs, distributions, and per-player data")
st.markdown("4. **AI Insights** — get AI-generated analysis of your results")
