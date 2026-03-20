"""Results section rendering for the simulation dashboard.

Renders the Charts tab, Churn Analysis tab, and Data Table tab.
Works with either a full ResultsDisplay object or a loaded summary from history.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import polars as pl
import streamlit as st

from src.domain.protocols import ResultsDisplay
from src.ui.components.distribution_chart import render_distribution_chart
from src.ui.components.segment_metrics import render_segment_metrics

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POINTS_HISTOGRAM_BINS = 30
_CHART_HEIGHT = 400
_CHART_COLOR_PRIMARY = "#FF6B35"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_results(
    display: ResultsDisplay | None,
    loaded_summary: dict[str, Any] | None,
    loaded_distribution: dict[str, Any] | None,
) -> None:
    """Render the Results section (Charts, Churn Analysis, Data Table).

    Args:
        display: A ResultsDisplay-compatible object (e.g. CoinFlipResult).
        loaded_summary: Summary dict from a loaded past run.
        loaded_distribution: Distribution dict from a loaded past run.
    """
    st.subheader("Results")

    # Get distribution from either full result or loaded history
    display_dist: dict[str, int] = {}
    if display is not None:
        display_dist = display.get_distribution()
    elif loaded_distribution:
        display_dist = {str(k): int(v) for k, v in loaded_distribution.items()}

    if display is not None:
        # Full result available -- show all tabs
        charts_tab, churn_tab, data_tab = st.tabs(
            ["Charts", "Churn Analysis", "Data Table"]
        )

        with charts_tab:
            _render_charts_tab(display, display_dist)

        with churn_tab:
            _render_churn_tab(display)

        with data_tab:
            _render_data_tab(display)

    else:
        # Loaded from history -- show distribution chart only (no player-level data)
        render_distribution_chart(
            distribution=display_dist,
            title="Success Depth Distribution",
            x_label="Success Depth",
            y_label="Interaction Count",
        )
        st.caption(
            "Showing summary from a past run. "
            "Upload player data and re-run for full charts, churn analysis, and data table."
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _render_charts_tab(
    display: ResultsDisplay,
    display_dist: dict[str, int],
) -> None:
    """Render the Charts tab with distribution and points histogram."""
    st.caption(
        "How points and flip outcomes are distributed across the player base. "
        "Each interaction is a coin-flip chain: flip up to max_successes times, "
        "stop on first tails. Points = cumulative sum of configured point values at each depth."
    )
    chart_left, chart_right = st.columns(2)
    with chart_left:
        render_distribution_chart(
            distribution=display_dist,
            title="Success Depth Distribution",
            x_label="Success Depth",
            y_label="Interaction Count",
        )
        st.caption(
            "X-axis: success depth = number of consecutive successful flips before first tails. "
            "Y-axis: count of interactions that ended at that depth. "
            "Depth 0 = tails on first flip (no points). "
            "Each flip i has probability p_success_i from config."
        )
    with chart_right:
        result_df = display.get_dataframe()
        if not result_df.is_empty() and "total_points" in result_df.columns:
            points_hist = (
                alt.Chart(result_df)
                .mark_bar(color=_CHART_COLOR_PRIMARY)
                .encode(
                    x=alt.X(
                        "total_points:Q",
                        bin=alt.Bin(maxbins=_POINTS_HISTOGRAM_BINS),
                        title="Total Points",
                    ),
                    y=alt.Y("count()", title="Number of Players"),
                    tooltip=[
                        alt.Tooltip(
                            "total_points:Q",
                            bin=alt.Bin(maxbins=_POINTS_HISTOGRAM_BINS),
                            title="Points Range",
                        ),
                        alt.Tooltip("count()", title="Players"),
                    ],
                )
                .properties(
                    title="Points Distribution Across Players",
                    width="container",
                    height=_CHART_HEIGHT,
                )
            )
            st.altair_chart(points_hist, use_container_width=True)
            st.caption(
                "X-axis: total_points per player = sum over all interactions of "
                "(cumulative points at success depth * avg_multiplier). "
                "Y-axis: number of players in that points range (histogram bins)."
            )


def _render_churn_tab(display: ResultsDisplay) -> None:
    """Render the Churn Analysis tab using segment data from ResultsDisplay."""
    st.caption(
        "Segments players by about_to_churn flag from CSV. "
        "Churn players: each flip probability is multiplied by churn_boost_multiplier (default 1.3x), "
        "capped at 1.0. This means boosted_p = min(p_success_i * 1.3, 1.0). "
        "Compare metrics to see the effect of the churn boost on earnings."
    )

    # Try protocol-based segment rendering first
    segments = display.get_segments()
    if segments is not None:
        # Render each segment side by side
        segment_names = list(segments.keys())
        cols = st.columns(len(segment_names))
        for col, seg_name in zip(cols, segment_names, strict=False):
            with col:
                title = seg_name.replace("-", " ").replace("_", " ").title()
                st.markdown(f"#### {title} Players")
                seg_metrics = segments[seg_name]
                player_count = int(seg_metrics.get("Player Count", 0))
                if player_count == 0:
                    st.info(f"No {seg_name} players in this dataset.")
                else:
                    _render_segment_kpis(seg_metrics, seg_name)
    else:
        # Fallback: try legacy DataFrame-based rendering
        result_df = display.get_dataframe()
        if "about_to_churn" in result_df.columns:
            churn_df = result_df.filter(pl.col("about_to_churn"))
            non_churn_df = result_df.filter(~pl.col("about_to_churn"))
            col_churn, col_non_churn = st.columns(2)
            with col_churn:
                st.markdown("#### About-to-Churn Players")
                render_segment_metrics(churn_df, "churn")
            with col_non_churn:
                st.markdown("#### Non-Churn Players")
                render_segment_metrics(non_churn_df, "non-churn")
        else:
            st.info("No churn data available.")


def _render_segment_kpis(metrics: dict[str, float], label: str) -> None:
    """Render KPI metrics for one segment from ResultsDisplay.get_segments()."""

    def _fmt_num(v: float) -> str:
        return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"

    player_count = int(metrics.get("Player Count", 0))
    st.metric(
        "Player Count",
        f"{player_count:,}",
        help=(
            f"Count of players in the **{label}** segment.\n\n"
            f"Segmented by the about_to_churn flag from the uploaded CSV."
        ),
    )
    st.metric(
        "Avg Points / Player",
        _fmt_num(metrics.get("Avg Points / Player", 0.0)),
        help=(
            f"**Calculation:** sum(total_points) / count(players) for {label} segment\n\n"
            f"**Churn boost:** players with about_to_churn=true get "
            f"boosted_p = min(p_success_i * 1.3, 1.0)\n"
            f"so their average is expected to be higher."
        ),
    )
    st.metric(
        "Median Points / Player",
        _fmt_num(metrics.get("Median Points / Player", 0.0)),
        help=(
            f"Middle value of total_points for **{label}** players when sorted.\n\n"
            f"Compare mean vs median to detect skew in the distribution."
        ),
    )
    st.metric(
        "Total Points",
        _fmt_num(metrics.get("Total Points", 0.0)),
        help=(
            f"**Calculation:** sum(total_points) for all {label} players\n\n"
            f"**Parameters:**\n"
            f"- total_points = sum over interactions of "
            f"(cumulative points at success depth * avg_multiplier)"
        ),
    )


def _render_data_tab(display: ResultsDisplay) -> None:
    """Render the Data Table tab with download button."""
    result_df = display.get_dataframe()
    # Cache CSV export in session state to avoid re-serializing on every rerun
    if "cached_csv_data" not in st.session_state:
        st.session_state["cached_csv_data"] = result_df.write_csv()
    csv_data = st.session_state["cached_csv_data"]
    st.download_button(
        "Download Results CSV",
        csv_data,
        "simulation_results.csv",
        "text/csv",
        key="download_results_csv",
        help="Download the full per-player results table as CSV. Includes user_id, total_points, num_interactions, and all original player columns.",
    )
    st.dataframe(result_df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {result_df.height:,} player rows.")
