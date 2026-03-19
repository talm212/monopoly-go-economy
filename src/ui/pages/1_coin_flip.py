"""Coin Flip Simulator — single-page feature with tabbed workflow.

Upload data, configure parameters, run simulation, and analyze results
all within one page using Streamlit tabs.
"""

from __future__ import annotations

import logging
from typing import Any

import altair as alt
import polars as pl
import streamlit as st

from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult
from src.domain.simulators.coin_flip import CoinFlipSimulator
from src.infrastructure.readers.local_reader import LocalDataReader
from src.infrastructure.readers.normalize import normalize_churn_column
from src.infrastructure.store.local_store import LocalSimulationStore
from src.ui.components.config_editor import render_config_editor
from src.ui.components.distribution_chart import render_distribution_chart
from src.ui.components.kpi_cards import render_kpi_cards
from src.ui.components.upload_widget import render_upload_widget

logger = logging.getLogger(__name__)

_reader = LocalDataReader()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POINTS_HISTOGRAM_BINS = 30
_CHART_HEIGHT = 400
_CHART_COLOR_PRIMARY = "#FF6B35"
_CHART_COLOR_CHURN = "#E63946"
_CHART_COLOR_NON_CHURN = "#457B9D"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _config_df_to_raw_dict(df: pl.DataFrame) -> dict[str, str]:
    """Convert a config CSV DataFrame (Input, Value columns) to a raw string dict."""
    raw: dict[str, str] = {}
    for row in df.iter_rows(named=True):
        raw[str(row["Input"])] = str(row["Value"])
    return raw


def _raw_dict_to_display(raw: dict[str, str]) -> dict[str, Any]:
    """Convert raw CSV string dict to display-friendly types for the editor."""
    display: dict[str, Any] = {}
    for key, value in raw.items():
        if value.endswith("%"):
            display[key] = value
        else:
            try:
                display[key] = int(value)
            except ValueError:
                try:
                    display[key] = float(value)
                except ValueError:
                    display[key] = value
    return display


def _display_dict_to_raw(display: dict[str, Any]) -> dict[str, str]:
    """Convert the editor's display dict back to raw string form."""
    raw: dict[str, str] = {}
    for key, value in display.items():
        if isinstance(value, str):
            raw[key] = value
        elif isinstance(value, float) and not isinstance(value, bool):
            if value == int(value):
                raw[key] = str(int(value))
            else:
                raw[key] = str(value)
        else:
            raw[key] = str(value)
    return raw


# ---------------------------------------------------------------------------
# Tab: Upload & Configure
# ---------------------------------------------------------------------------


def _render_upload_tab() -> None:
    """Upload player data and config CSVs, edit parameters."""

    # --- Player data upload ---
    st.subheader("Player Data")
    player_df = render_upload_widget(
        label="Upload player CSV (user_id, rolls_sink, avg_multiplier, about_to_churn)",
        accepted_types=["csv"],
        key="cf_player_upload",
    )

    if player_df is not None:
        validation_errors = _reader.validate_players(player_df)
        if validation_errors:
            for err in validation_errors:
                st.error(err)
        else:
            st.success("Player data is valid.")
            st.metric("Total players", f"{player_df.height:,}")
            with st.expander("Preview (first 10 rows)", expanded=False):
                st.dataframe(player_df.head(10), use_container_width=True)

            player_df = normalize_churn_column(player_df)
            st.session_state["player_data"] = player_df
    else:
        st.info("Please upload a player CSV to get started.")

    st.markdown("---")

    # --- Config CSV upload ---
    st.subheader("Simulation Config")
    config_df = render_upload_widget(
        label="Upload config CSV (Input, Value columns)",
        accepted_types=["csv"],
        key="cf_config_upload",
    )

    if config_df is not None:
        try:
            raw_config = _config_df_to_raw_dict(config_df)
            display_config = _raw_dict_to_display(raw_config)
            st.success(f"Parsed **{len(raw_config)}** config parameters.")
            with st.expander("Raw config table", expanded=False):
                st.dataframe(config_df, use_container_width=True)
            st.session_state["config_dict"] = display_config
        except Exception:
            logger.exception("Failed to parse config CSV")
            st.error("Failed to parse config CSV. Ensure it has 'Input' and 'Value' columns.")
    elif "config_dict" not in st.session_state:
        st.info("Please upload a config CSV, or use the default editor below.")

    st.markdown("---")

    # --- Config editor ---
    st.subheader("Edit Parameters")
    if "config_dict" in st.session_state:
        current_config = st.session_state["config_dict"]
        edited_config = render_config_editor(current_config, key_prefix="cf_cfg")
        st.session_state["config_dict"] = edited_config

        try:
            raw_for_model = _display_dict_to_raw(edited_config)
            coin_flip_config = CoinFlipConfig.from_csv_dict(raw_for_model)
            coin_flip_config.validate()
            st.session_state["config"] = coin_flip_config
        except (KeyError, ValueError) as exc:
            st.error(f"Config validation error: {exc}")
            st.session_state.pop("config", None)
    else:
        st.info("Upload a config CSV above to populate the editor.")

    st.markdown("---")

    # --- Readiness summary ---
    has_players = "player_data" in st.session_state
    has_config = "config" in st.session_state
    col1, col2 = st.columns(2)
    with col1:
        if has_players:
            st.success(f"Player data: {st.session_state['player_data'].height:,} rows")
        else:
            st.warning("Player data: not uploaded")
    with col2:
        if has_config:
            st.success(f"Config: {st.session_state['config'].max_successes} flip depths")
        else:
            st.warning("Config: not set")

    if has_players and has_config:
        st.success("Ready to simulate! Switch to the **Run** tab.")


# ---------------------------------------------------------------------------
# Tab: Run Simulation
# ---------------------------------------------------------------------------


def _render_run_tab() -> None:
    """Execute the simulation and show quick summary."""
    player_data = st.session_state.get("player_data")
    config: CoinFlipConfig | None = st.session_state.get("config")

    if player_data is None or config is None:
        st.warning("Please upload data and config in the **Upload & Configure** tab first.")
        return

    # Config summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Max Successes", config.max_successes)
    with col2:
        st.metric("Churn Boost", f"{config.churn_boost_multiplier:.1f}x")
    with col3:
        st.metric("Reward Threshold", f"{config.reward_threshold:,.0f}")

    with st.expander("Flip probabilities & point values", expanded=False):
        prob_strs = [f"{p:.1%}" for p in config.probabilities]
        point_strs = [f"{v:g}" for v in config.point_values]
        st.markdown(
            f"**Probabilities:** {', '.join(prob_strs)}  \n"
            f"**Point values:** {', '.join(point_strs)}"
        )

    st.markdown("---")

    # Controls
    seed_input = st.number_input(
        "Random seed (optional, for reproducibility)",
        min_value=0,
        max_value=2**31 - 1,
        value=None,
        step=1,
        placeholder="Leave empty for random",
        key="cf_seed",
    )
    seed: int | None = int(seed_input) if seed_input is not None else None

    if st.button("Run Simulation", type="primary", use_container_width=True, key="cf_run"):
        try:
            with st.spinner("Running simulation..."):
                simulator = CoinFlipSimulator()
                result = simulator.simulate(player_data, config, seed=seed)

            st.session_state["simulation_result"] = result

            # Auto-save to history
            try:
                store = LocalSimulationStore()
                store.save_run(
                    {
                        "feature": "coin_flip",
                        "config": config.to_dict(),
                        "result_summary": result.to_summary_dict(),
                        "distribution": result.get_distribution(),
                    }
                )
            except Exception:
                logger.exception("Failed to auto-save simulation run")

            st.success(
                f"Simulation complete — {result.total_interactions:,} interactions "
                f"across {player_data.height:,} players."
            )
        except Exception:
            logger.exception("Simulation failed")
            st.error("Simulation failed. Check data and configuration.")

    # Show results if available
    result: CoinFlipResult | None = st.session_state.get("simulation_result")
    if result is not None:
        st.markdown("---")
        st.subheader("Quick Summary")
        raw_kpis = result.get_kpi_metrics()
        render_kpi_cards(
            {
                "Mean Points / Player": raw_kpis["mean_points_per_player"],
                "Median Points / Player": raw_kpis["median_points_per_player"],
                "Total Points": raw_kpis["total_points"],
                "% Above Threshold": round(raw_kpis["pct_above_threshold"] * 100, 2),
            },
            columns=4,
        )

        distribution = result.get_distribution()
        if distribution:
            chart_data = {"Depth": list(distribution.keys()), "Count": list(distribution.values())}
            st.bar_chart(chart_data, x="Depth", y="Count", use_container_width=True)

        st.info("Switch to the **Results** tab for detailed analysis.")


# ---------------------------------------------------------------------------
# Tab: Results & Analysis
# ---------------------------------------------------------------------------


def _render_results_tab() -> None:
    """Detailed visualization of simulation outcomes."""
    result: CoinFlipResult | None = st.session_state.get("simulation_result")
    if result is None:
        st.warning("No simulation results. Run a simulation in the **Run** tab first.")
        return

    player_results = result.player_results

    # KPI Cards
    st.subheader("Key Performance Indicators")
    raw = result.get_kpi_metrics()
    render_kpi_cards(
        {
            "Mean Points / Player": raw["mean_points_per_player"],
            "Median Points / Player": raw["median_points_per_player"],
            "Total Points": raw["total_points"],
            "% Above Threshold": round(raw["pct_above_threshold"] * 100, 2),
        },
        columns=4,
    )

    # CSV Download
    csv_data = result.to_dataframe().write_csv()
    st.download_button("Download Results CSV", csv_data, "simulation_results.csv", "text/csv")

    st.markdown("---")

    # Success Distribution
    st.subheader("Success Distribution")
    render_distribution_chart(
        distribution=result.get_distribution(),
        title="Success Depth Distribution",
        x_label="Success Depth",
        y_label="Interaction Count",
    )

    st.markdown("---")

    # Points Histogram
    st.subheader("Points Distribution")
    if not player_results.is_empty():
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

    st.markdown("---")

    # Churn vs Non-Churn
    st.subheader("Churn vs Non-Churn Comparison")
    if "about_to_churn" in player_results.columns:
        churn_df = player_results.filter(pl.col("about_to_churn"))
        non_churn_df = player_results.filter(~pl.col("about_to_churn"))

        col_churn, col_non_churn = st.columns(2)
        with col_churn:
            st.markdown("#### About-to-Churn Players")
            _render_segment_metrics(churn_df, "churn")
        with col_non_churn:
            st.markdown("#### Non-Churn Players")
            _render_segment_metrics(non_churn_df, "non-churn")

    st.markdown("---")

    # Data Table
    st.subheader("Player-Level Data")
    with st.expander("Detailed Player Results", expanded=False):
        st.dataframe(player_results, use_container_width=True, hide_index=True)
        st.caption(f"Showing {player_results.height:,} player rows.")


def _render_segment_metrics(segment: pl.DataFrame, label: str) -> None:
    """Render KPI metrics for a player segment."""
    if segment.height == 0:
        st.info(f"No {label} players in this dataset.")
        return

    points_col = segment["total_points"]
    mean_val = float(points_col.mean() or 0.0)
    median_val = float(points_col.median() or 0.0)
    total_val = float(points_col.sum() or 0.0)

    st.metric("Player Count", f"{segment.height:,}")
    st.metric("Avg Points / Player", f"{mean_val:,.2f}")
    st.metric("Median Points / Player", f"{median_val:,.2f}")
    st.metric("Total Points", f"{total_val:,.0f}")


# ---------------------------------------------------------------------------
# Page layout — tabbed
# ---------------------------------------------------------------------------

st.header("Coin Flip Simulator")
st.markdown("Upload data, configure parameters, run simulation, and analyze results.")

tab_upload, tab_run, tab_results = st.tabs(
    [
        "Upload & Configure",
        "Run Simulation",
        "Results & Analysis",
    ]
)

with tab_upload:
    _render_upload_tab()

with tab_run:
    _render_run_tab()

with tab_results:
    _render_results_tab()
