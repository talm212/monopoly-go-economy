"""AI Insights dashboard — LLM-powered analysis of simulation results."""

from __future__ import annotations

import logging
import os

import streamlit as st

from src.application.analyze_results import InsightsAnalyst
from src.domain.models.coin_flip import CoinFlipResult
from src.domain.models.insight import Insight, Severity
from src.infrastructure.llm.client import get_llm_client
from src.ui.async_helper import run_async

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.INFO: "#1E88E5",
    Severity.WARNING: "#FB8C00",
    Severity.CRITICAL: "#E53935",
}

_SEVERITY_LABELS: dict[Severity, str] = {
    Severity.INFO: "INFO",
    Severity.WARNING: "WARNING",
    Severity.CRITICAL: "CRITICAL",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_severity_badge(severity: Severity) -> str:
    """Return an HTML badge span for the given severity level."""
    color = _SEVERITY_COLORS[severity]
    label = _SEVERITY_LABELS[severity]
    return (
        f'<span style="background-color:{color};color:white;'
        f"padding:2px 10px;border-radius:12px;font-size:0.85em;"
        f'font-weight:600;">{label}</span>'
    )


def _render_insight_card(insight: Insight) -> None:
    """Render a single insight as a styled card."""
    badge_html = _render_severity_badge(insight.severity)

    st.markdown(
        f"{badge_html}&ensp;**{insight.finding}**",
        unsafe_allow_html=True,
    )
    st.markdown(f"*Recommendation:* {insight.recommendation}")

    if insight.metric_references:
        with st.expander("Supporting Metrics", expanded=False):
            rows = [
                {"Metric": name, "Value": value}
                for name, value in insight.metric_references.items()
            ]
            st.table(rows)

    st.markdown("---")


def _run_generate_insights(
    result: CoinFlipResult,
    config_dict: dict,
) -> list[Insight]:
    """Run the async generate_insights in a synchronous context."""
    llm_client = get_llm_client()
    analyst = InsightsAnalyst(llm_client)

    result_summary = result.to_summary_dict()
    distribution = result.get_distribution()
    kpi_metrics = result.get_kpi_metrics()

    return run_async(
        analyst.generate_insights(
            result_summary=result_summary,
            distribution=distribution,
            config=config_dict,
            kpi_metrics=kpi_metrics,
            feature_name="coin flip",
        )
    )


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.header("AI Insights")
st.markdown(
    "LLM-powered analysis of your simulation results. "
    "Generates actionable insights for the economy team."
)

# ---- Prerequisite check ---------------------------------------------------

result: CoinFlipResult | None = st.session_state.get("simulation_result")

if result is None:
    st.warning(
        "No simulation results found. "
        "Please run a simulation first on the **Run Simulation** page."
    )
    st.page_link("pages/2_run_simulation.py", label="Go to Run Simulation")
    st.stop()

# ---- API key check --------------------------------------------------------

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")

if llm_provider == "anthropic" and not api_key:
    st.error(
        "**ANTHROPIC_API_KEY not set.**\n\n"
        "To use AI Insights, set the `ANTHROPIC_API_KEY` environment variable:\n\n"
        "```bash\n"
        "export ANTHROPIC_API_KEY='sk-ant-...'\n"
        "```\n\n"
        "Then restart the Streamlit app. "
        "Alternatively, set `LLM_PROVIDER=bedrock` to use AWS Bedrock."
    )
    st.stop()

# ---- Config retrieval -----------------------------------------------------

config_dict: dict = {}
config_obj = st.session_state.get("config")
if config_obj is not None and hasattr(config_obj, "to_dict"):
    config_dict = config_obj.to_dict()

# ---- Generate / Regenerate buttons ----------------------------------------

existing_insights: list[Insight] | None = st.session_state.get("ai_insights")

col_gen, col_regen = st.columns([1, 1])

generate_clicked = False
regenerate_clicked = False

with col_gen:
    if existing_insights is None:
        generate_clicked = st.button(
            "Generate Insights",
            type="primary",
            use_container_width=True,
        )

with col_regen:
    if existing_insights is not None:
        regenerate_clicked = st.button(
            "Regenerate Insights",
            type="secondary",
            use_container_width=True,
        )

# ---- Insight generation ---------------------------------------------------

if generate_clicked or regenerate_clicked:
    with st.spinner("Analyzing simulation results with AI..."):
        try:
            insights = _run_generate_insights(result, config_dict)
            if insights:
                st.session_state["ai_insights"] = insights
                logger.info("Generated %d AI insights", len(insights))
                st.rerun()
            else:
                st.warning(
                    "The AI did not return any insights. "
                    "This may indicate an issue with the LLM response. "
                    "Please try again."
                )
        except ValueError as exc:
            st.error(f"Configuration error: {exc}")
            logger.exception("LLM configuration error")
        except Exception:
            st.error(
                "Failed to generate insights. "
                "Please check your API key and network connection, then try again."
            )
            logger.exception("Unexpected error generating insights")

# ---- Render cached insights -----------------------------------------------

cached_insights: list[Insight] | None = st.session_state.get("ai_insights")

if cached_insights:
    st.subheader(f"Analysis ({len(cached_insights)} insights)")
    for insight in cached_insights:
        _render_insight_card(insight)
elif existing_insights is None and not generate_clicked:
    st.info("Click **Generate Insights** to analyze your simulation results with AI.")
