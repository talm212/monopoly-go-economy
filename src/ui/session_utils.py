"""Shared session state utilities for the Streamlit dashboard."""
from __future__ import annotations

import streamlit as st


def clear_stale_ai_data() -> None:
    """Clear AI-related session state when simulation results change."""
    for key in (
        "ai_insights", "ai_chat_history", "optimizer_steps",
        "optimizer_best_config", "cached_csv_data",
        "optimizer_original_config", "optimizer_original_kpis",
        "optimizer_original_distribution", "optimizer_optimized_kpis",
        "optimizer_optimized_distribution",
    ):
        st.session_state.pop(key, None)


def config_changed_since_last_run() -> bool:
    """Check whether the config has been edited since the last simulation run."""
    return bool(st.session_state.get("config_changed_since_run", False))
