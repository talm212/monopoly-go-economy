"""Coin Flip Economy Simulator — single-page Streamlit application.

Consolidates the entire simulation workflow into one scrollable page:
Setup (upload + config) -> KPI Bar -> Results (charts, churn, data) ->
AI Analysis (insights, chat, optimizer).  History lives in the sidebar drawer.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import altair as alt
import polars as pl
import streamlit as st

from src.application.analyze_results import InsightsAnalyst
from src.application.chat_assistant import ChatAssistant
from src.application.optimize_config import ConfigOptimizer
from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult
from src.domain.models.insight import Insight, Severity
from src.domain.models.optimization import (
    OptimizationDirection,
    OptimizationStep,
    OptimizationTarget,
)
from src.domain.simulators.coin_flip import CoinFlipSimulator
from src.infrastructure.llm.client import get_llm_client
from src.infrastructure.readers.local_reader import LocalDataReader
from src.infrastructure.readers.normalize import normalize_churn_column
from src.infrastructure.store.local_store import LocalSimulationStore
from src.ui.async_helper import run_async
from src.ui.components.ai_chat_panel import render_ai_chat_panel
from src.ui.components.comparison_view import render_comparison_view
from src.ui.components.config_editor import render_config_editor
from src.ui.components.distribution_chart import render_distribution_chart
from src.ui.components.kpi_cards import render_kpi_cards
from src.ui.components.upload_widget import render_upload_widget

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POINTS_HISTOGRAM_BINS = 30
_CHART_HEIGHT = 400
_CHART_COLOR_PRIMARY = "#FF6B35"
_CHART_COLOR_CHURN = "#E63946"
_CHART_COLOR_NON_CHURN = "#457B9D"

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

_MAX_DISPLAY_RUNS = 50
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_OPTIMIZER_METRICS = (
    "pct_above_threshold",
    "mean_points_per_player",
    "total_points",
)

_DIRECTION_OPTIONS = {
    "Target": OptimizationDirection.TARGET,
    "Maximize": OptimizationDirection.MAXIMIZE,
    "Minimize": OptimizationDirection.MINIMIZE,
}

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

_reader = LocalDataReader()


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


def _config_obj_to_display(config: CoinFlipConfig) -> dict[str, Any]:
    """Convert a CoinFlipConfig to the display dict format the editor expects.

    The editor uses CSV-style keys (p_success_1, points_success_1, etc.)
    while the config object stores flat lists.
    """
    display: dict[str, Any] = {}
    for i, p in enumerate(config.probabilities, 1):
        display[f"p_success_{i}"] = f"{round(p * 100):.0f}%"
    for i, v in enumerate(config.point_values, 1):
        display[f"points_success_{i}"] = int(v) if v == int(v) else v
    display["max_successes"] = config.max_successes
    return display


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------


def _format_timestamp(iso_str: str) -> str:
    """Format an ISO timestamp to a human-readable string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime(_DATE_FORMAT)
    except (ValueError, TypeError):
        return iso_str


def _format_run_label(run: dict[str, Any]) -> str:
    """Build a short label for a run suitable for selectbox display."""
    created = _format_timestamp(run.get("created_at", ""))
    name = run.get("name", "")
    feature = run.get("feature", "unknown")
    summary = run.get("result_summary", {})
    total_pts = summary.get("total_points", 0)
    try:
        label = name if name else feature
        return f"{created} | {label} | {float(total_pts):,.0f} pts"
    except (ValueError, TypeError):
        return f"{created} | {name or feature}"


# ---------------------------------------------------------------------------
# Insight rendering helpers
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


# ---------------------------------------------------------------------------
# Segment metrics helper
# ---------------------------------------------------------------------------


def _render_segment_metrics(segment: pl.DataFrame, label: str) -> None:
    """Render KPI metrics for a player segment (churn / non-churn)."""
    if segment.height == 0:
        st.info(f"No {label} players in this dataset.")
        return

    points_col = segment["total_points"]
    mean_val = float(points_col.mean() or 0.0)
    median_val = float(points_col.median() or 0.0)
    total_val = float(points_col.sum() or 0.0)

    def _fmt_num(v: float) -> str:
        return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"

    st.metric(
        "Player Count", f"{segment.height:,}",
        help=(
            f"Count of players in the **{label}** segment.\n\n"
            f"Segmented by the about_to_churn flag from the uploaded CSV."
        ),
    )
    st.metric(
        "Avg Points / Player", _fmt_num(mean_val),
        help=(
            f"**Calculation:** sum(total_points) / count(players) for {label} segment\n\n"
            f"**Churn boost:** players with about_to_churn=true get "
            f"boosted_p = min(p_success_i * 1.3, 1.0)\n"
            f"so their average is expected to be higher."
        ),
    )
    st.metric(
        "Median Points / Player", _fmt_num(median_val),
        help=(
            f"Middle value of total_points for **{label}** players when sorted.\n\n"
            f"Compare mean vs median to detect skew in the distribution."
        ),
    )
    st.metric(
        "Total Points", _fmt_num(total_val),
        help=(
            f"**Calculation:** sum(total_points) for all {label} players\n\n"
            f"**Parameters:**\n"
            f"- total_points = sum over interactions of "
            f"(cumulative points at success depth * avg_multiplier)"
        ),
    )


# ---------------------------------------------------------------------------
# Stale data helpers
# ---------------------------------------------------------------------------


def _clear_stale_ai_data() -> None:
    """Clear AI-related session state when simulation results change."""
    for key in ("ai_insights", "ai_chat_history", "optimizer_steps", "optimizer_best_config"):
        st.session_state.pop(key, None)


def _config_changed_since_last_run() -> bool:
    """Check whether the config has been edited since the last simulation run."""
    return bool(st.session_state.get("config_changed_since_run", False))


# ---------------------------------------------------------------------------
# Setup summary builder
# ---------------------------------------------------------------------------


def _build_setup_summary() -> str:
    """Build a one-line summary for the collapsed setup expander label."""
    parts: list[str] = []

    player_data: pl.DataFrame | None = st.session_state.get("player_data")
    if player_data is not None:
        parts.append(f"{player_data.height:,} players")

    config: CoinFlipConfig | None = st.session_state.get("config")
    if config is not None:
        parts.append(f"{config.max_successes} depths")
        parts.append(f"threshold {config.reward_threshold:,.0f}")

    if parts:
        return "Setup -- " + ", ".join(parts)
    return "Setup"


# ===========================================================================
# Page configuration
# ===========================================================================

st.set_page_config(
    page_title="Coin Flip Economy Simulator",
    page_icon="\U0001f3b2",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===========================================================================
# Persistence: load most recent run on startup
# ===========================================================================

store = LocalSimulationStore()

# Load last run config ONLY on first app load (not on every rerun)
if not st.session_state.get("_app_initialized", False):
    st.session_state["_app_initialized"] = True
    try:
        recent_runs = store.list_runs(limit=1)
        if recent_runs:
            last_run = recent_runs[0]
            config_data = last_run.get("config", {})
            if config_data:
                try:
                    loaded_config = CoinFlipConfig.from_dict(config_data)
                    st.session_state["config"] = loaded_config
                    st.session_state["config_dict"] = _config_obj_to_display(
                        loaded_config
                    )
                except (KeyError, ValueError):
                    logger.warning("Could not restore config from last run")
    except Exception:
        logger.exception("Failed to load most recent run")


# ===========================================================================
# 1. HEADER
# ===========================================================================

st.title("Coin Flip Economy Simulator")

# Injected CSS: sticky KPI bar
st.markdown(
    """<style>
    /* Sticky KPI bar */
    [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="sticky-kpi-bar"]) {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: var(--background-color, white);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>""",
    unsafe_allow_html=True,
)



# ===========================================================================
# HISTORY (sidebar — open via hamburger menu, always available)
# ===========================================================================

with st.sidebar:
    st.header("History")

    all_runs = store.list_runs(limit=_MAX_DISPLAY_RUNS)

    if not all_runs:
        st.info("No past runs yet. Run a simulation to see history here.")
    else:
        st.write(f"**{len(all_runs)}** run(s)")

        for idx, run in enumerate(all_runs):
            with st.container(border=True):
                created = _format_timestamp(run.get("created_at", ""))
                summary = run.get("result_summary", {})
                total_pts = summary.get("total_points", 0)
                run_name = run.get("name", "")
                run_id = run.get("run_id", "")

                st.caption(f"{created} — {float(total_pts):,.0f} pts")

                # Editable name — saves on change, key tied to run_id for stability
                new_name = st.text_input(
                    "Run name",
                    value=run_name,
                    key=f"name_{run_id}",
                    placeholder="Name this run...",
                    label_visibility="collapsed",
                )
                if new_name != run_name and run_id:
                    try:
                        store.update_run(run_id, {"name": new_name})
                    except Exception:
                        logger.warning("Failed to rename run %s", run_id)

                load_col, delete_col = st.columns(2)
                with load_col:
                    if st.button("Load", key=f"load_run_{idx}", use_container_width=True):
                        run_config = run.get("config", {})
                        try:
                            if run_config:
                                loaded_cfg = CoinFlipConfig.from_dict(run_config)
                                st.session_state["config"] = loaded_cfg
                                st.session_state["config_dict"] = _config_obj_to_display(
                                    loaded_cfg
                                )
                                st.session_state["config_uploaded"] = True

                            # Load result summary + distribution for display
                            run_summary = run.get("result_summary", {})
                            run_dist = run.get("distribution", {})
                            if run_summary:
                                st.session_state["loaded_run_summary"] = run_summary
                                st.session_state["loaded_run_distribution"] = run_dist
                                # Clear full result so loaded view takes over
                                st.session_state.pop("simulation_result", None)
                                _clear_stale_ai_data()

                            st.toast(f"Loaded run from {created}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to load run: {exc}")
                with delete_col:
                    if st.button("Delete", key=f"del_run_{idx}", use_container_width=True):
                        try:
                            store.delete_run(run["run_id"])
                            st.toast("Run deleted.")
                            st.rerun()
                        except FileNotFoundError:
                            st.warning("Run already deleted.")

        # --- Compare two runs ---
        st.markdown("---")
        st.subheader("Compare Runs")

        if len(all_runs) < 2:
            st.info("Need at least 2 runs to compare.")
        else:
            run_labels = {r["run_id"]: _format_run_label(r) for r in all_runs}
            run_ids = list(run_labels.keys())

            selected_a = st.selectbox(
                "Run A",
                options=run_ids,
                format_func=lambda x: run_labels.get(x, x),
                index=0,
                key="sidebar_compare_a",
            )
            default_b = 1 if len(run_ids) > 1 else 0
            selected_b = st.selectbox(
                "Run B",
                options=run_ids,
                format_func=lambda x: run_labels.get(x, x),
                index=default_b,
                key="sidebar_compare_b",
            )

            if selected_a and selected_b and selected_a != selected_b:
                if st.button("Compare Side-by-Side", type="primary", use_container_width=True):
                    st.session_state["comparison_mode"] = True
                    st.session_state["comparison_runs"] = (
                        store.get_run(selected_a),
                        store.get_run(selected_b),
                    )
                    st.rerun()
            elif selected_a == selected_b:
                st.warning("Select two different runs.")


# ===========================================================================
# Comparison mode overlay
# ===========================================================================

if st.session_state.get("comparison_mode", False):
    comparison_runs = st.session_state.get("comparison_runs")
    if comparison_runs:
        run_a_data, run_b_data = comparison_runs
        if st.button("Back to Current Simulation"):
            st.session_state["comparison_mode"] = False
            st.session_state.pop("comparison_runs", None)
            st.rerun()

        render_comparison_view(
            run_a=run_a_data,
            run_b=run_b_data,
            label_a=_format_run_label(run_a_data),
            label_b=_format_run_label(run_b_data),
        )
        st.stop()


# ===========================================================================
# 2. SETUP SECTION
# ===========================================================================

has_result = "simulation_result" in st.session_state

# After first run: collapsible expander with summary. Before: regular heading.
if has_result:
    _setup_container = st.expander(_build_setup_summary(), expanded=False)
else:
    st.subheader("Setup")
    _setup_container = st.container()

with _setup_container:
    # --- Two-column upload ---
    upload_left, upload_right = st.columns(2)

    with upload_left:
        st.markdown("#### Player Data")
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
                player_df = normalize_churn_column(player_df)
                st.session_state["player_data"] = player_df

    with upload_right:
        st.markdown("#### Configuration")
        config_df = render_upload_widget(
            label="Upload config CSV (Input, Value columns)",
            accepted_types=["csv"],
            key="cf_config_upload",
        )

        if config_df is not None:
            try:
                raw_config = _config_df_to_raw_dict(config_df)
                display_config = _raw_dict_to_display(raw_config)
                st.session_state["config_dict"] = display_config
                st.session_state["config_uploaded"] = True
            except Exception:
                logger.exception("Failed to parse config CSV")
                st.error("Failed to parse config CSV. Ensure it has 'Input' and 'Value' columns.")

    # --- Config editor (only after user uploads config or loads from history) ---
    if st.session_state.get("config_uploaded", False) and "config_dict" in st.session_state:
        with st.expander("Edit Config...", expanded=False):
            current_display = st.session_state["config_dict"]
            edited_config = render_config_editor(current_display, key_prefix="cf_cfg")

            # Only rebuild CoinFlipConfig if the user actually changed something.
            # On first render after Load, widgets may return defaults — skip validation.
            if edited_config != current_display:
                st.session_state["config_changed_since_run"] = True
                st.session_state["config_dict"] = edited_config

                try:
                    raw_for_model = _display_dict_to_raw(edited_config)
                    coin_flip_config = CoinFlipConfig.from_csv_dict(raw_for_model)
                    st.session_state["config"] = coin_flip_config
                except (KeyError, ValueError) as exc:
                    st.error(f"Config validation error: {exc}")
                    st.session_state.pop("config", None)

    # (Seed + Run button are placed outside the setup container below)

# --- Seed + Run button + readiness (always visible) ---
has_players = "player_data" in st.session_state
has_config = "config" in st.session_state

# Status message
_has_loaded_summary = st.session_state.get("loaded_run_summary") is not None
_has_sim_result = "simulation_result" in st.session_state
if has_players and has_config:
    st.success("Ready to simulate")
elif _has_loaded_summary and not _has_sim_result and has_config and not has_players:
    st.warning("Upload player data to re-run with this config")
elif not has_players and not has_config:
    st.info("Upload player data and config to get started")
elif not has_players:
    st.warning("Upload player data to continue")
else:
    st.warning("Upload config to continue")

seed_col, run_col = st.columns([1, 3])

with seed_col:
    seed_input = st.number_input(
        "Seed (optional)",
        min_value=0,
        max_value=2**31 - 1,
        value=None,
        step=1,
        placeholder="Random",
        key="cf_seed",
        help=(
            "Seeds the NumPy random number generator.\n\n"
            "All coin flip outcomes are generated at once as a random matrix.\n"
            "Same seed + same data + same config = identical results every time."
        ),
    )
    seed: int | None = int(seed_input) if seed_input is not None else None

with run_col:
    run_disabled = not (has_players and has_config)
    st.markdown(
        '<p style="font-size:14px;margin-bottom:4px;">&nbsp;</p>',
        unsafe_allow_html=True,
    )
    run_clicked = st.button(
        "Run Simulation",
        type="primary",
        use_container_width=True,
        key="cf_run",
        disabled=run_disabled,
    )

# --- Execute simulation ---
if run_clicked and has_players and has_config:
    player_data_run: pl.DataFrame = st.session_state["player_data"]
    config_run: CoinFlipConfig = st.session_state["config"]

    try:
        with st.spinner("Running simulation..."):
            simulator = CoinFlipSimulator()
            result = simulator.simulate(player_data_run, config_run, seed=seed)

        st.session_state["simulation_result"] = result
        st.session_state["config_changed_since_run"] = False

        # Clear stale AI data
        _clear_stale_ai_data()

        # Auto-save to history (include KPI metrics for loaded view)
        _save_summary = result.to_summary_dict()
        _save_summary.update(result.get_kpi_metrics())
        try:
            store.save_run(
                {
                    "feature": "coin_flip",
                    "config": config_run.to_dict(),
                    "result_summary": _save_summary,
                    "distribution": result.get_distribution(),
                }
            )
        except Exception:
            logger.exception("Failed to auto-save simulation run")

        st.success(
            f"Simulation complete -- {result.total_interactions:,} interactions "
            f"across {player_data_run.height:,} players."
        )
        st.rerun()

    except Exception:
        logger.exception("Simulation failed")
        st.error("Simulation failed. Check data and configuration.")

# --- Stale config warning ---
if _config_changed_since_last_run() and has_result:
    st.warning("Config changed since last run. Re-run to update results.")


# ===========================================================================
# 3. KPI BAR
# ===========================================================================

sim_result: CoinFlipResult | None = st.session_state.get("simulation_result")
loaded_summary: dict[str, Any] | None = st.session_state.get("loaded_run_summary")
loaded_distribution: dict[str, Any] | None = st.session_state.get("loaded_run_distribution")

has_any_result = sim_result is not None or loaded_summary is not None

if has_any_result:
    if loaded_summary and sim_result is None:
        st.info("Showing results from a past run. Upload player data and re-run for full analysis.")

    _KPI_HELP = {
        "Mean Points / Player": (
            "**Calculation:** sum(total_points) / count(players)\n\n"
            "**Parameters:**\n"
            "- total_points per player = sum of points from all their coin-flip interactions\n"
            "- Per interaction: flip up to max_successes times, stop at first tails\n"
            "- Points = cumulative sum of points_success_1..points_success_depth\n"
            "- Final points multiplied by the player's avg_multiplier"
        ),
        "Median Points / Player": (
            "**Calculation:** middle value when all players' total_points are sorted\n\n"
            "Less sensitive to outliers than the mean.\n"
            "If mean >> median, a few players earn disproportionately more."
        ),
        "Total Points": (
            "**Calculation:** sum(total_points) across all players\n\n"
            "**Parameters:**\n"
            "- total_points per player = sum over interactions of "
            "(cumulative points at success depth * avg_multiplier)\n"
            "- Reflects the total economy output of the simulation"
        ),
        "% Above Threshold": (
            "**Calculation:** count(players where total_points > threshold) "
            "/ count(players) * 100\n\n"
            "**Parameters:**\n"
            "- reward_threshold: set in config (default 100)\n"
            "- Shows what fraction of players exceed the reward cutoff"
        ),
        "Total Interactions": (
            "**Calculation:** sum(rolls_sink // avg_multiplier) for each player\n\n"
            "**Parameters:**\n"
            "- rolls_sink: total rolls available to the player (from CSV)\n"
            "- avg_multiplier: average bet multiplier (from CSV)\n"
            "- Each interaction triggers one coin-flip chain"
        ),
        "Players Above Threshold": (
            "**Calculation:** count of players where total_points > reward_threshold\n\n"
            "- reward_threshold is set in config (default 100)"
        ),
        "Threshold": (
            "The reward_threshold config parameter.\n\n"
            "Players with total_points above this value are counted in "
            "'Players Above Threshold' and '% Above Threshold'."
        ),
    }

    with st.container(border=True):
        st.markdown('<div data-testid="sticky-kpi-bar"></div>', unsafe_allow_html=True)
        if sim_result is not None:
            raw_kpis = sim_result.get_kpi_metrics()
            render_kpi_cards(
                {
                    "Mean Points / Player": raw_kpis["mean_points_per_player"],
                    "Median Points / Player": raw_kpis["median_points_per_player"],
                    "Total Points": raw_kpis["total_points"],
                    "% Above Threshold": round(raw_kpis["pct_above_threshold"] * 100, 2),
                },
                columns=4,
                help_texts=_KPI_HELP,
            )
        elif loaded_summary:
            # Show same 4 KPIs as fresh run if available, else fall back
            _loaded_mean = loaded_summary.get("mean_points_per_player")
            _loaded_median = loaded_summary.get("median_points_per_player")
            _loaded_pct = loaded_summary.get("pct_above_threshold")

            if _loaded_mean is not None:
                # New format: full KPIs saved
                render_kpi_cards(
                    {
                        "Mean Points / Player": _loaded_mean,
                        "Median Points / Player": _loaded_median or 0,
                        "Total Points": loaded_summary.get("total_points", 0),
                        "% Above Threshold": round(float(_loaded_pct or 0) * 100, 2),
                    },
                    columns=4,
                    help_texts=_KPI_HELP,
                )
            else:
                # Old format: only basic summary saved
                render_kpi_cards(
                    {
                        "Total Interactions": loaded_summary.get("total_interactions", 0),
                        "Total Points": loaded_summary.get("total_points", 0),
                        "Players Above Threshold": loaded_summary.get("players_above_threshold", 0),
                        "Threshold": loaded_summary.get("threshold", 100),
                    },
                    columns=4,
                    help_texts=_KPI_HELP,
                )



# ===========================================================================
# 4. RESULTS SECTION
# ===========================================================================

if has_any_result:
    st.subheader("Results")

    # Get distribution from either full result or loaded history
    display_dist: dict[str, int] = {}
    if sim_result is not None:
        display_dist = sim_result.get_distribution()
    elif loaded_distribution:
        display_dist = {str(k): int(v) for k, v in loaded_distribution.items()}

    if sim_result is not None:
        # Full result available — show all tabs
        charts_tab, churn_tab, data_tab = st.tabs(
            ["Charts", "Churn Analysis", "Data Table"]
        )

        with charts_tab:
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

        with churn_tab:
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
                    _render_segment_metrics(churn_df, "churn")
                with col_non_churn:
                    st.markdown("#### Non-Churn Players")
                    _render_segment_metrics(non_churn_df, "non-churn")
            else:
                st.info("No churn data available.")

        with data_tab:
            result_df = sim_result.to_dataframe()
            csv_data = result_df.write_csv()
            st.download_button(
                "Download Results CSV",
                csv_data,
                "simulation_results.csv",
                "text/csv",
                key="download_results_csv",
            )
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            st.caption(f"Showing {result_df.height:,} player rows.")

    else:
        # Loaded from history — show distribution chart only (no player-level data)
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


# ===========================================================================
# 5. AI ANALYSIS SECTION
# ===========================================================================

if has_any_result:
    st.subheader("AI Analysis")

    if _config_changed_since_last_run():
        st.warning(
            "Config has changed since the last simulation. "
            "AI analysis is based on previous results."
        )

    st.caption(
        "AI-powered analysis of your simulation results. "
        "Requires an LLM provider (Bedrock or Anthropic) to be configured."
    )
    insights_tab, chat_tab, optimizer_tab = st.tabs(
        [
            "Insights",
            "Ask a Question",
            "Optimizer",
        ]
    )

    # Build shared context for AI — from full result or loaded summary
    _config_obj: CoinFlipConfig | None = st.session_state.get("config")
    _config_dict_for_ai: dict[str, Any] = _config_obj.to_dict() if _config_obj is not None else {}

    if sim_result is not None:
        _result_summary = sim_result.to_summary_dict()
        _distribution = sim_result.get_distribution()
        _kpi_metrics = sim_result.get_kpi_metrics()
    elif loaded_summary:
        _result_summary = loaded_summary
        _distribution = {str(k): int(v) for k, v in (loaded_distribution or {}).items()}
        _kpi_metrics = {
            "total_points": loaded_summary.get("total_points", 0),
            "mean_points_per_player": 0.0,
            "median_points_per_player": 0.0,
            "pct_above_threshold": 0.0,
        }
    else:
        _result_summary = {}
        _distribution = {}
        _kpi_metrics = {}

    # --- Insights tab ---
    with insights_tab:
        st.caption(
            "AI reviews your simulation KPIs and flags findings ranked by severity: "
            "INFO (observation), WARNING (potential issue), CRITICAL (requires attention)."
        )
        existing_insights: list[Insight] | None = st.session_state.get("ai_insights")

        button_label = "Regenerate Insights" if existing_insights else "Generate Insights"
        generate_clicked = st.button(
            button_label,
            type="primary",
            use_container_width=True,
            key="ai_generate_insights",
        )

        if generate_clicked:
            with st.spinner("Analyzing simulation results with AI..."):
                try:
                    llm_client = get_llm_client()
                    analyst = InsightsAnalyst(llm_client)

                    insights = run_async(
                        analyst.generate_insights(
                            result_summary=_result_summary,
                            distribution=_distribution,
                            config=_config_dict_for_ai,
                            kpi_metrics=_kpi_metrics,
                            feature_name="coin flip",
                        )
                    )
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
                except Exception as exc:
                    st.error(
                        f"Failed to generate insights: `{type(exc).__name__}: {exc}`\n\n"
                        f"Check your LLM provider config (LLM_PROVIDER, AWS credentials, or ANTHROPIC_API_KEY)."
                    )
                    logger.exception("Unexpected error generating insights")

        # Render cached insights
        cached_insights: list[Insight] | None = st.session_state.get("ai_insights")
        if cached_insights:
            st.caption(f"{len(cached_insights)} insight(s) generated")
            for insight in cached_insights:
                _render_insight_card(insight)
        elif not generate_clicked:
            st.info("Click **Generate Insights** to analyze your simulation results with AI.")

    # --- Ask a Question tab ---
    with chat_tab:
        st.caption(
            "Chat with AI about your simulation results. Ask about trends, "
            "anomalies, or what-if scenarios."
        )
        try:
            llm_client_chat = get_llm_client()
            assistant = ChatAssistant(llm_client_chat)

            render_ai_chat_panel(
                assistant=assistant,
                result_summary=_result_summary,
                distribution=_distribution,
                config=_config_dict_for_ai,
                kpi_metrics=_kpi_metrics,
            )
        except ValueError as exc:
            st.error(f"LLM configuration error: {exc}")
        except Exception:
            st.error("Failed to initialize chat assistant. Check your LLM configuration.")
            logger.exception("Chat assistant initialization failed")

    # --- Optimizer tab ---
    with optimizer_tab:
        st.caption(
            "AI iteratively tunes coin-flip config parameters to reach a target KPI value. "
            "Each iteration runs a full simulation."
        )
        opt_col_left, opt_col_right = st.columns(2)

        with opt_col_left:
            target_metric = st.selectbox(
                "Target metric",
                options=list(_OPTIMIZER_METRICS),
                index=0,
                key="opt_target_metric",
                help=(
                    "**Metrics:**\n"
                    "- **pct_above_threshold** = count(players where total_points > threshold) / count(players)\n"
                    "- **mean_points_per_player** = sum(total_points) / count(players)\n"
                    "- **total_points** = sum of all players' total_points\n\n"
                    "The AI adjusts probabilities and point values to move this metric toward your target."
                ),
            )
            target_value = st.number_input(
                "Target value",
                value=5.0,
                step=0.1,
                format="%.4f",
                key="opt_target_value",
                help="The desired value for the selected metric.\n\nThe optimizer will try to make the metric converge to this number.",
            )

        with opt_col_right:
            direction_label = st.selectbox(
                "Direction",
                options=list(_DIRECTION_OPTIONS.keys()),
                index=0,
                key="opt_direction",
                help=(
                    "- **Target:** converge to the exact target value\n"
                    "- **Maximize:** push metric as high as possible\n"
                    "- **Minimize:** push metric as low as possible"
                ),
            )
            max_iterations = st.number_input(
                "Max iterations",
                min_value=1,
                max_value=20,
                value=10,
                step=1,
                key="opt_max_iter",
                help="How many optimization rounds the AI will attempt before stopping.\n\nEach iteration runs a full simulation with adjusted config.",
            )

        optimize_clicked = st.button(
            "Run Optimizer",
            type="primary",
            use_container_width=True,
            key="opt_run",
        )

        if optimize_clicked:
            player_data_opt: pl.DataFrame | None = st.session_state.get("player_data")
            config_opt: CoinFlipConfig | None = st.session_state.get("config")

            if player_data_opt is None:
                st.error("Upload player data first to run the optimizer.")
            elif config_opt is None:
                st.error("Set a configuration first to run the optimizer.")
            else:
                direction = _DIRECTION_OPTIONS[direction_label]
                target = OptimizationTarget(
                    metric=target_metric,
                    target_value=float(target_value),
                    direction=direction,
                )

                def _simulate_fn(
                    cfg_dict: dict[str, Any],
                    players: pl.DataFrame,
                ) -> dict[str, Any]:
                    """Simulate wrapper for the optimizer."""
                    cfg = CoinFlipConfig.from_dict(cfg_dict)
                    sim = CoinFlipSimulator()
                    res = sim.simulate(players, cfg)
                    summary = res.to_summary_dict()
                    summary.update(res.get_kpi_metrics())
                    return summary

                with st.spinner("Running optimizer (this may take a minute)..."):
                    try:
                        llm_client_opt = get_llm_client()
                        optimizer = ConfigOptimizer(
                            llm_client=llm_client_opt,
                            max_iterations=int(max_iterations),
                        )

                        best_config, steps = run_async(
                            optimizer.optimize(
                                simulate_fn=_simulate_fn,
                                current_config=config_opt.to_dict(),
                                target=target,
                                players=player_data_opt,
                            )
                        )

                        st.session_state["optimizer_steps"] = steps
                        st.session_state["optimizer_best_config"] = best_config
                        logger.info("Optimizer finished: %d steps", len(steps))

                    except Exception:
                        st.error("Optimizer failed. Check LLM configuration and try again.")
                        logger.exception("Optimizer failed")

        # Display optimizer results
        opt_steps: list[OptimizationStep] | None = st.session_state.get("optimizer_steps")
        opt_best: dict[str, Any] | None = st.session_state.get("optimizer_best_config")

        if opt_steps:
            st.markdown("#### Iteration Log")

            step_rows = [
                {
                    "Iteration": s.iteration,
                    "Metric Value": round(s.result_metric, 6),
                    "Distance to Target": round(s.distance_to_target, 6),
                }
                for s in opt_steps
            ]
            step_df = pl.DataFrame(step_rows)
            st.dataframe(step_df, use_container_width=True, hide_index=True)

            # Convergence status
            final_step = opt_steps[-1]
            tv = float(target_value) if float(target_value) != 0 else 1.0
            if final_step.distance_to_target < 0.05 * abs(tv):
                st.success(f"Converged at iteration {final_step.iteration}")
            else:
                st.warning(
                    f"Did not converge within {len(opt_steps)} iteration(s). "
                    f"Best distance: {final_step.distance_to_target:.4f}"
                )

        if opt_best:
            st.markdown("#### Best Config Found")
            st.json(opt_best)

            if st.button(
                "Apply Best Config & Re-run",
                type="primary",
                use_container_width=True,
                key="opt_apply",
            ):
                try:
                    # Write optimized config to session state
                    applied_config = CoinFlipConfig.from_dict(opt_best)
                    st.session_state["config"] = applied_config
                    st.session_state["config_dict"] = _config_obj_to_display(applied_config)

                    # Auto-run if player data exists
                    player_data_apply: pl.DataFrame | None = st.session_state.get("player_data")
                    if player_data_apply is not None:
                        simulator = CoinFlipSimulator()
                        new_result = simulator.simulate(player_data_apply, applied_config)
                        st.session_state["simulation_result"] = new_result
                        st.session_state["config_changed_since_run"] = False

                        # Auto-save (include KPI metrics for loaded view)
                        _opt_summary = new_result.to_summary_dict()
                        _opt_summary.update(new_result.get_kpi_metrics())
                        try:
                            store.save_run(
                                {
                                    "feature": "coin_flip",
                                    "config": applied_config.to_dict(),
                                    "result_summary": _opt_summary,
                                    "distribution": new_result.get_distribution(),
                                }
                            )
                        except Exception:
                            logger.exception("Failed to auto-save optimized run")

                    # Clear stale AI data
                    _clear_stale_ai_data()
                    st.rerun()

                except (KeyError, ValueError) as exc:
                    st.error(f"Failed to apply config: {exc}")
                    logger.exception("Failed to apply optimizer config")


# ===========================================================================
# Empty state placeholder (when no results yet)
# ===========================================================================

if not has_any_result:
    st.markdown("---")
    st.info(
        "No simulation results yet. "
        "Upload player data and config above, then run a simulation."
    )
