"""Reusable insight card rendering components.

Generic UI components for rendering AI-generated insights with severity
badges. Works for any feature's AI insights (coin flip, loot tables, etc.).
"""

from __future__ import annotations

import streamlit as st

from src.domain.models.insight import Insight, Severity

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_COLORS: dict[Severity, str] = {
    Severity.INFO: "#1E88E5",
    Severity.WARNING: "#FB8C00",
    Severity.CRITICAL: "#E53935",
}

SEVERITY_LABELS: dict[Severity, str] = {
    Severity.INFO: "INFO",
    Severity.WARNING: "WARNING",
    Severity.CRITICAL: "CRITICAL",
}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def render_severity_badge(severity: Severity) -> str:
    """Return an HTML badge span for the given severity level."""
    color = SEVERITY_COLORS[severity]
    label = SEVERITY_LABELS[severity]
    return (
        f'<span style="background-color:{color};color:white;'
        f"padding:2px 10px;border-radius:12px;font-size:0.85em;"
        f'font-weight:600;">{label}</span>'
    )


def render_insight_card(insight: Insight) -> None:
    """Render a single insight as a styled card."""
    badge_html = render_severity_badge(insight.severity)

    st.markdown(badge_html, unsafe_allow_html=True)
    st.markdown(f"**{insight.finding}**")
    st.markdown(f"*Recommendation:* {insight.recommendation}")

    if insight.metric_references:
        with st.expander("Supporting Metrics", expanded=False):
            rows = [
                {"Metric": name, "Value": value}
                for name, value in insight.metric_references.items()
            ]
            st.table(rows)

    st.markdown("---")
