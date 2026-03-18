"""Results visualization & KPI dashboard — detailed analysis of simulation outcomes."""
from __future__ import annotations

import logging

import altair as alt
import polars as pl
import streamlit as st

from src.domain.models.coin_flip import CoinFlipResult
from src.ui.components.distribution_chart import render_distribution_chart
from src.ui.components.kpi_cards import render_kpi_cards

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POINTS_HISTOGRAM_BINS = 30
_CHART_HEIGHT = 400
_CHART_COLOR_PRIMARY = "#FF6B35"
_CHART_COLOR_CHURN = "#E63946"
_CHART_COLOR_NON_CHURN = "#457B9D"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_kpi_display(result: CoinFlipResult) -> dict[str, float | int]:
    """Map raw KPI metrics to human-readable labels."""
    raw = result.get_kpi_metrics()
    return {
        "Mean Points / Player": raw["mean_points_per_player"],
        "Median Points / Player": raw["median_points_per_player"],
        "Total Points": raw["total_points"],
        "% Above Threshold": round(raw["pct_above_threshold"] * 100, 2),
    }


def _render_points_histogram(player_results: pl.DataFrame) -> None:
    """Render a histogram of total_points across all players."""
    if player_results.is_empty():
        st.info("No player results to display.")
        return

    chart = (
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
    st.altair_chart(chart, use_container_width=True)


def _render_churn_comparison(player_results: pl.DataFrame) -> None:
    """Render side-by-side metrics comparing churn vs non-churn players."""
    if "about_to_churn" not in player_results.columns:
        st.warning("Churn status column not found in player results.")
        return

    churn_df = player_results.filter(pl.col("about_to_churn") == True)  # noqa: E712
    non_churn_df = player_results.filter(pl.col("about_to_churn") == False)  # noqa: E712

    col_churn, col_non_churn = st.columns(2)

    with col_churn:
        st.markdown("#### About-to-Churn Players")
        _render_segment_metrics(churn_df, label="churn")

    with col_non_churn:
        st.markdown("#### Non-Churn Players")
        _render_segment_metrics(non_churn_df, label="non-churn")


def _render_segment_metrics(segment: pl.DataFrame, label: str) -> None:
    """Render KPI metrics for a player segment (churn or non-churn)."""
    player_count = segment.height
    if player_count == 0:
        st.info(f"No {label} players in this dataset.")
        return

    points_col = segment["total_points"]
    mean_val = points_col.mean()
    median_val = points_col.median()
    total_val = points_col.sum()

    avg_points = float(mean_val) if mean_val is not None else 0.0
    median_points = float(median_val) if median_val is not None else 0.0
    total_points = float(total_val) if total_val is not None else 0.0

    # Compute average interactions if column exists
    interactions_col = segment.get_column("num_interactions") if "num_interactions" in segment.columns else None
    avg_interactions: float = 0.0
    if interactions_col is not None:
        interactions_mean = interactions_col.mean()
        avg_interactions = float(interactions_mean) if interactions_mean is not None else 0.0

    st.metric("Player Count", f"{player_count:,}")
    st.metric("Avg Points / Player", f"{avg_points:,.2f}")
    st.metric("Median Points / Player", f"{median_points:,.2f}")
    st.metric("Total Points", f"{total_points:,.0f}")
    st.metric("Avg Interactions", f"{avg_interactions:,.1f}")

    logger.debug(
        "Segment %s: %d players, avg_points=%.2f",
        label,
        player_count,
        avg_points,
    )


def _render_data_table(player_results: pl.DataFrame) -> None:
    """Render the full player results in a sortable, expandable data table."""
    with st.expander("Detailed Player Results", expanded=False):
        st.dataframe(
            player_results,
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Showing {player_results.height:,} player rows.")


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.header("Results & Analysis")
st.markdown(
    "Detailed visualization of simulation outcomes including KPIs, "
    "distributions, and churn analysis."
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

logger.info(
    "Rendering results page: %d interactions, %.0f total points",
    result.total_interactions,
    result.total_points,
)

player_results = result.player_results

# ---- Section 1: KPI Cards ------------------------------------------------

st.subheader("Key Performance Indicators")
kpi_display = _build_kpi_display(result)
render_kpi_cards(kpi_display, columns=4)

# ---- CSV Download --------------------------------------------------------

csv_data = result.to_dataframe().write_csv()
st.download_button(
    "Download Results CSV",
    csv_data,
    "simulation_results.csv",
    "text/csv",
)

st.markdown("---")

# ---- Section 2: Success Distribution Chart --------------------------------

st.subheader("Success Distribution")
st.markdown(
    "Number of interactions that ended at each success depth "
    "(0 = immediate tails, higher = more consecutive heads)."
)
distribution = result.get_distribution()
render_distribution_chart(
    distribution=distribution,
    title="Success Depth Distribution",
    x_label="Success Depth",
    y_label="Interaction Count",
)

st.markdown("---")

# ---- Section 3: Points Distribution Histogram ----------------------------

st.subheader("Points Distribution")
st.markdown("How total points are distributed across all players.")
_render_points_histogram(player_results)

st.markdown("---")

# ---- Section 4: Churn vs Non-Churn Comparison ----------------------------

st.subheader("Churn vs Non-Churn Comparison")
st.markdown(
    "Side-by-side comparison of simulation outcomes for players "
    "flagged as about-to-churn versus non-churn players."
)
_render_churn_comparison(player_results)

st.markdown("---")

# ---- Section 5: Detailed Data Table --------------------------------------

st.subheader("Player-Level Data")
_render_data_table(player_results)
