"""Reusable insight card rendering components.

Generic UI components for rendering AI-generated insights with severity
badges. Works for any feature's AI insights (coin flip, loot tables, etc.).
When an insight includes a sweep suggestion, renders a button that
populates the Parameter Sweep section with the recommended values.
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


def render_insight_card(insight: Insight, card_index: int = 0) -> None:
    """Render a single insight as a styled card.

    Args:
        insight: The Insight to render.
        card_index: Index for unique widget keys when rendering multiple cards.
    """
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

    # Sweep suggestion button (getattr for backward compat with cached insights)
    if getattr(insight, "sweep_suggestion", None) is not None:
        sweep = insight.sweep_suggestion
        sweep_label = (
            f"Sweep {sweep.parameter}: "
            f"{sweep.start} \u2192 {sweep.end} ({sweep.steps} steps)"
        )
        if sweep.reason:
            st.caption(f"Suggested sweep: {sweep.reason}")

        if st.button(
            sweep_label,
            key=f"insight_sweep_{card_index}",
            use_container_width=True,
            help=(
                f"Pre-fill the Parameter Sweep section with: "
                f"{sweep.parameter} from {sweep.start} to {sweep.end} "
                f"in {sweep.steps} steps. Scroll down to Parameter Sweep to run it."
            ),
        ):
            st.session_state["sweep_prefill"] = {
                "parameter": sweep.parameter,
                "start": sweep.start,
                "end": sweep.end,
                "steps": sweep.steps,
            }
            st.toast(
                f"Sweep pre-filled: {sweep.parameter} "
                f"{sweep.start} \u2192 {sweep.end}. "
                f"Scroll down to Parameter Sweep to run it."
            )
            st.rerun()

    st.markdown("---")
