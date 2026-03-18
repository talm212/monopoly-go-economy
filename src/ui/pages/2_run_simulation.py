"""Run Simulation page — execute coin-flip simulation and display quick summary."""
from __future__ import annotations

import logging

import streamlit as st

from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult
from src.domain.simulators.coin_flip import CoinFlipSimulator
from src.infrastructure.store.local_store import LocalSimulationStore
from src.ui.components.kpi_cards import render_kpi_cards

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_config_summary(config: CoinFlipConfig) -> None:
    """Display a compact summary of the current simulation configuration."""
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


def _render_success_distribution(result: CoinFlipResult) -> None:
    """Show the success depth distribution as a bar chart preview."""
    distribution = result.get_distribution()
    if not distribution:
        return

    chart_data = {
        "Depth": [f"Depth {k}" for k in distribution],
        "Count": list(distribution.values()),
    }
    st.bar_chart(chart_data, x="Depth", y="Count", use_container_width=True)


def _render_kpi_summary(result: CoinFlipResult) -> None:
    """Render KPI cards with human-readable labels."""
    raw_kpis = result.get_kpi_metrics()

    display_kpis: dict[str, float | int] = {
        "Mean Points / Player": raw_kpis["mean_points_per_player"],
        "Median Points / Player": raw_kpis["median_points_per_player"],
        "Total Points": raw_kpis["total_points"],
        "% Above Threshold": round(raw_kpis["pct_above_threshold"] * 100, 2),
    }
    render_kpi_cards(display_kpis, columns=4)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.header("Run Simulation")
st.markdown("Execute the coin-flip simulation with the uploaded data and configuration.")

# ---- Prerequisite check ---------------------------------------------------

player_data = st.session_state.get("player_data")
config = st.session_state.get("config")

if player_data is None or config is None:
    st.warning(
        "Player data and/or configuration not found. "
        "Please go to **Upload & Configure** to load your data first."
    )
    st.page_link("pages/1_upload_configure.py", label="Go to Upload & Configure")
    st.stop()

# ---- Config summary -------------------------------------------------------

st.subheader("Current Configuration")
_render_config_summary(config)

st.markdown("---")

# ---- Simulation controls --------------------------------------------------

st.subheader("Simulation Controls")

seed_input = st.number_input(
    "Random seed (optional, for reproducibility)",
    min_value=0,
    max_value=2**31 - 1,
    value=None,
    step=1,
    placeholder="Leave empty for random",
)

seed: int | None = int(seed_input) if seed_input is not None else None

run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)

# ---- Execute simulation ---------------------------------------------------

if run_clicked:
    try:
        with st.spinner("Running simulation..."):
            simulator = CoinFlipSimulator()
            result = simulator.simulate(player_data, config, seed=seed)

        st.session_state["simulation_result"] = result
        logger.info(
            "Simulation completed: %d interactions, %.0f total points",
            result.total_interactions,
            result.total_points,
        )

        # Auto-save to simulation history
        try:
            store = LocalSimulationStore()
            store.save_run({
                "feature": "coin_flip",
                "config": config.to_dict(),
                "result_summary": result.to_summary_dict(),
                "distribution": result.get_distribution(),
            })
            logger.info("Simulation run auto-saved to history")
        except Exception:
            logger.exception("Failed to auto-save simulation run to history")

        st.success(
            f"Simulation complete — {result.total_interactions:,} interactions "
            f"across {player_data.height:,} players."
        )
    except Exception:
        logger.exception("Simulation failed")
        st.error(
            "Simulation failed. Please check your data and configuration, "
            "then try again. See logs for details."
        )

# ---- Results summary (persists across reruns) -----------------------------

result: CoinFlipResult | None = st.session_state.get("simulation_result")

if result is not None:
    st.markdown("---")
    st.subheader("Quick Summary")

    _render_kpi_summary(result)

    st.markdown("#### Success Distribution")
    _render_success_distribution(result)

    st.info("Navigate to the **Results** page for detailed analysis and export options.")
