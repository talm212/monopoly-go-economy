"""Main entry point for the Monopoly Go Economy Simulator dashboard."""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Monopoly Go Economy Simulator",
    page_icon="\U0001f3b2",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar
st.sidebar.title("Economy Simulator")
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")
# Pages will be added as features are built

st.title("Monopoly Go Economy Simulator")
st.markdown("Welcome to the economy simulation platform. Use the sidebar to navigate.")
st.markdown("### Quick Start")
st.markdown("1. **Upload** player data and config CSVs")
st.markdown("2. **Configure** simulation parameters")
st.markdown("3. **Run** the simulation")
st.markdown("4. **Analyze** results with AI insights")
