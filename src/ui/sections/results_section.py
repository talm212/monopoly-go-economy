"""Results section rendering for the simulation dashboard.

Renders the Charts tab, Churn Analysis tab, and Data Table tab.
Works with either a full simulation result or a loaded summary from history.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import polars as pl
import streamlit as st

from src.domain.models.coin_flip import CoinFlipResult
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
    sim_result: CoinFlipResult | None,
    loaded_summary: dict[str, Any] | None,
    loaded_distribution: dict[str, Any] | None,
) -> None:
    """Render the Results section (Charts, Churn Analysis, Data Table).

    Args:
        sim_result: Full simulation result (if a fresh simulation was run).
        loaded_summary: Summary dict from a loaded past run.
        loaded_distribution: Distribution dict from a loaded past run.
    """
    st.subheader("Results")

    # Get distribution from either full result or loaded history
    display_dist: dict[str, int] = {}
    if sim_result is not None:
        display_dist = sim_result.get_distribution()
    elif loaded_distribution:
        display_dist = {str(k): int(v) for k, v in loaded_distribution.items()}

    if sim_result is not None:
        # Full result available -- show all tabs
        charts_tab, churn_tab, data_tab = st.tabs(
            ["Charts", "Churn Analysis", "Data Table"]
        )

        with charts_tab:
            _render_charts_tab(sim_result, display_dist)

        with churn_tab:
            _render_churn_tab(sim_result)

        with data_tab:
            _render_data_tab(sim_result)

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
    sim_result: CoinFlipResult,
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
        player_results = sim_result.player_results
        if not player_results.is_empty():
            points_hist = (
                alt.Chart(player_results)
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


def _render_churn_tab(sim_result: CoinFlipResult) -> None:
    """Render the Churn Analysis tab."""
    player_results = sim_result.player_results
    st.caption(
        "Segments players by about_to_churn flag from CSV. "
        "Churn players: each flip probability is multiplied by churn_boost_multiplier (default 1.3x), "
        "capped at 1.0. This means boosted_p = min(p_success_i * 1.3, 1.0). "
        "Compare metrics to see the effect of the churn boost on earnings."
    )
    if "about_to_churn" in player_results.columns:
        churn_df = player_results.filter(pl.col("about_to_churn"))
        non_churn_df = player_results.filter(~pl.col("about_to_churn"))
        col_churn, col_non_churn = st.columns(2)
        with col_churn:
            st.markdown("#### About-to-Churn Players")
            render_segment_metrics(churn_df, "churn")
        with col_non_churn:
            st.markdown("#### Non-Churn Players")
            render_segment_metrics(non_churn_df, "non-churn")
    else:
        st.info("No churn data available.")


def _render_data_tab(sim_result: CoinFlipResult) -> None:
    """Render the Data Table tab with download button."""
    result_df = sim_result.to_dataframe()
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
    )
    st.dataframe(result_df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {result_df.height:,} player rows.")
