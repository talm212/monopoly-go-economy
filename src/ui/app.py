"""Economy Simulator — single-page Streamlit application with feature routing.

Thin orchestrator that wires together section modules:
Setup (upload + config) -> KPI Bar -> Results (charts, churn, data) ->
AI Analysis (insights, chat, optimizer).  History lives in the sidebar drawer.

The active feature is selected via ``?feature=`` query parameter (defaults to
coin_flip).  Each registered feature renders its own UI; unimplemented features
show a "Coming soon" placeholder.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl
import streamlit as st

from src.application.config_conversion import (
    config_df_to_raw_dict,
    config_obj_to_display,
    display_dict_to_raw,
    raw_dict_to_display,
)
from src.application.run_simulation import RunSimulationUseCase
from src.domain.models.coin_flip import (
    CoinFlipConfig,
    CoinFlipResult,
    _KPI_HELP as _COIN_FLIP_KPI_HELP,
)
from src.domain.simulators.coin_flip import CoinFlipSimulator
from src.infrastructure.readers.local_reader import LocalDataReader
from src.infrastructure.readers.normalize import normalize_churn_column
from src.infrastructure.store.local_store import LocalSimulationStore
from src.ui.components.config_editor import render_config_editor
from src.ui.components.kpi_cards import render_kpi_cards
from src.ui.components.upload_widget import render_upload_widget
from src.ui.feature_router import (
    DEFAULT_FEATURE,
    FEATURE_REGISTRY,
    FeatureUIConfig,
    get_feature_config,
    is_valid_feature,
    list_feature_names,
)
from src.ui.sections.ai_analysis import render_ai_analysis
from src.ui.sections.results_section import render_results
from src.ui.sections.sidebar_history import render_sidebar_history

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backward-compatible aliases (used by tests that import from app.py)
# ---------------------------------------------------------------------------

_config_df_to_raw_dict = config_df_to_raw_dict
_raw_dict_to_display = raw_dict_to_display
_display_dict_to_raw = display_dict_to_raw
_config_obj_to_display = config_obj_to_display

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# KPI help texts: canonical source is in the domain model.
_KPI_HELP: dict[str, str] = {**_COIN_FLIP_KPI_HELP}

# ---------------------------------------------------------------------------
# Cached resource factories
# ---------------------------------------------------------------------------


@st.cache_resource
def _get_store() -> LocalSimulationStore:
    """Return a singleton LocalSimulationStore (cached across reruns)."""
    return LocalSimulationStore()


@st.cache_resource
def _get_reader() -> LocalDataReader:
    """Return a singleton LocalDataReader (cached across reruns)."""
    return LocalDataReader()


@st.cache_resource
def _get_use_case() -> RunSimulationUseCase:
    """Return a singleton RunSimulationUseCase wired with CoinFlipSimulator."""
    return RunSimulationUseCase(
        reader=_get_reader(),
        simulator=CoinFlipSimulator(),
    )


@st.cache_resource
def _get_llm_client():  # noqa: ANN202
    """Return a singleton LLM client (cached across reruns)."""
    from src.infrastructure.llm.client import get_llm_client

    return get_llm_client()


# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

store = _get_store()
_reader = _get_reader()
_use_case = _get_use_case()


# ---------------------------------------------------------------------------
# Feature routing helpers
# ---------------------------------------------------------------------------


def _resolve_current_feature() -> str:
    """Read the current feature from query params, falling back to default.

    If the query param value is not a registered feature, resets to the default.
    """
    params = st.query_params
    raw_feature = params.get("feature", DEFAULT_FEATURE)
    if is_valid_feature(raw_feature):
        return raw_feature
    # Invalid feature in URL — reset to default
    params["feature"] = DEFAULT_FEATURE
    return DEFAULT_FEATURE


# ---------------------------------------------------------------------------
# Stale data helpers
# ---------------------------------------------------------------------------


def _clear_stale_ai_data() -> None:
    """Clear AI-related session state when simulation results change."""
    for key in (
        "ai_insights", "ai_chat_history", "optimizer_steps",
        "optimizer_best_config", "cached_csv_data",
    ):
        st.session_state.pop(key, None)


def _config_changed_since_last_run() -> bool:
    """Check whether the config has been edited since the last simulation run."""
    return bool(st.session_state.get("config_changed_since_run", False))


# ===========================================================================
# Page configuration
# ===========================================================================

st.set_page_config(
    page_title="Economy Simulator",
    page_icon="\U0001f3b2",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ===========================================================================
# Feature routing
# ===========================================================================

current_feature = _resolve_current_feature()
current_feature_config: FeatureUIConfig | None = get_feature_config(current_feature)

# Ensure query param is always in sync
if st.query_params.get("feature") != current_feature:
    st.query_params["feature"] = current_feature


# ===========================================================================
# Persistence: load most recent run on startup
# ===========================================================================

# Load last run config ONLY on first app load (not on every rerun)
if not st.session_state.get("_app_initialized", False):
    st.session_state["_app_initialized"] = True
    st.session_state["config_changed_since_run"] = False
    try:
        recent_runs = store.list_runs(feature=current_feature, limit=1)
        if recent_runs:
            last_run = recent_runs[0]
            config_data = last_run.get("config", {})
            if config_data:
                try:
                    loaded_config = CoinFlipConfig.from_dict(config_data)
                    st.session_state["config"] = loaded_config
                    st.session_state["config_dict"] = config_obj_to_display(
                        loaded_config
                    )
                    st.session_state["_config_just_loaded"] = True
                except (KeyError, ValueError):
                    logger.warning("Could not restore config from last run")
    except Exception:
        logger.exception("Failed to load most recent run")


# ===========================================================================
# 1. HEADER with feature selector
# ===========================================================================

_feature_names = list_feature_names()

if current_feature_config is not None:
    _page_title = f"{current_feature_config.icon} {current_feature_config.display_name} Economy Simulator"
else:
    _page_title = "Economy Simulator"

st.title(_page_title)

# Feature selector — only shown when multiple features exist
if len(_feature_names) > 1:
    _display_index = _feature_names.index(current_feature) if current_feature in _feature_names else 0
    selected_feature = st.selectbox(
        "Feature",
        options=_feature_names,
        index=_display_index,
        format_func=lambda f: f"{FEATURE_REGISTRY[f].icon} {FEATURE_REGISTRY[f].display_name}",
        key="feature_selector",
    )
    if selected_feature != current_feature:
        st.query_params["feature"] = selected_feature
        st.rerun()

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
# HISTORY (sidebar) — filtered by current feature
# ===========================================================================

render_sidebar_history(store, feature=current_feature)


# ===========================================================================
# Feature guard — only coin_flip has a full UI for now
# ===========================================================================

if current_feature != "coin_flip":
    # Placeholder for future features
    st.markdown("---")
    _cfg = get_feature_config(current_feature)
    _display = _cfg.display_name if _cfg else current_feature
    st.info(
        f"**{_display}** simulator is coming soon. "
        "Stay tuned for updates!"
    )
    st.stop()


# ===========================================================================
# Comparison mode overlay
# ===========================================================================

if st.session_state.get("comparison_mode", False):
    comparison_runs = st.session_state.get("comparison_runs")
    if comparison_runs:
        from src.ui.components.comparison_view import render_comparison_view
        from src.ui.sections.sidebar_history import _format_run_label

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
# 2. SETUP SECTION (coin_flip)
# ===========================================================================

has_result = "simulation_result" in st.session_state

# After first run: collapsible expander with summary. Before: regular heading.
if has_result:
    _setup_container = st.expander("Setup", expanded=False)
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
                raw_config = config_df_to_raw_dict(config_df)
                display_config = raw_dict_to_display(raw_config)
                st.session_state["config_dict"] = display_config
                st.session_state["config_uploaded"] = True
                st.session_state["_config_just_loaded"] = True
                # Purge stale config editor widget keys
                for _k in list(st.session_state.keys()):
                    if _k.startswith("cf_cfg_"):
                        del st.session_state[_k]
            except Exception:
                logger.exception("Failed to parse config CSV")
                st.error("Failed to parse config CSV. Ensure it has 'Input' and 'Value' columns.")

    # --- Config editor (only after user uploads config or loads from history) ---
    if st.session_state.get("config_uploaded", False) and "config_dict" in st.session_state:
        with st.expander("Edit Config...", expanded=False):
            current_display = st.session_state["config_dict"]
            edited_config = render_config_editor(current_display, key_prefix="cf_cfg")

            # Only rebuild CoinFlipConfig if the user actually changed something.
            # Skip on first render after Load — widgets return defaults before they
            # pick up the loaded values.
            _skip_change_check = st.session_state.pop("_config_just_loaded", False)
            if not _skip_change_check and edited_config != current_display:
                st.session_state["config_changed_since_run"] = True
                st.session_state["config_dict"] = edited_config

                try:
                    raw_for_model = display_dict_to_raw(edited_config)
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
        help=(
            "Runs the coin-flip simulation for all uploaded players using the current config.\n\n"
            "Each player gets `rolls_sink / avg_multiplier` interactions. "
            "Each interaction is a flip chain up to `max_successes` depth. "
            "Results auto-save to history."
        ),
    )

# --- Execute simulation ---
if run_clicked and has_players and has_config:
    player_data_run: pl.DataFrame = st.session_state["player_data"]
    config_run: CoinFlipConfig = st.session_state["config"]

    try:
        with st.spinner("Running simulation..."):
            result = _use_case.execute_from_dataframe(player_data_run, config_run, seed=seed)

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
                },
                player_results=result.player_results,
            )
        except Exception:
            logger.exception("Failed to auto-save simulation run")

        st.toast(
            f"Simulation complete — {result.total_interactions:,} interactions "
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

    with st.container(border=True):
        st.markdown('<div data-testid="sticky-kpi-bar"></div>', unsafe_allow_html=True)
        if sim_result is not None:
            # Use the ResultsDisplay protocol: get_kpi_cards() returns
            # {label: (value, help_text)} — unpack for render_kpi_cards().
            kpi_cards = sim_result.get_kpi_cards()
            render_kpi_cards(
                {label: value for label, (value, _) in kpi_cards.items()},
                columns=3,
                help_texts={label: help_text for label, (_, help_text) in kpi_cards.items()},
            )
        elif loaded_summary:
            render_kpi_cards(
                {
                    "Total Interactions": loaded_summary.get("total_interactions", 0),
                    "Total Points": loaded_summary.get("total_points", 0),
                    "Players Above Threshold": loaded_summary.get("players_above_threshold", 0),
                },
                columns=3,
                help_texts=_KPI_HELP,
            )


# ===========================================================================
# 4. RESULTS SECTION
# ===========================================================================

if has_any_result:
    render_results(sim_result, loaded_summary, loaded_distribution)


# -- Download Report button --
if has_any_result:
    from src.ui.components.report_download import render_report_download

    # Gather data for the PDF report from whichever source is available
    _report_config: dict[str, Any] = {}
    _report_kpis: dict[str, float] = {}
    _report_dist: dict[str, int] = {}
    _report_segments: dict[str, dict[str, float]] | None = None
    _report_insights: list[dict[str, Any]] | None = st.session_state.get("ai_insights")

    if sim_result is not None:
        _report_kpis = sim_result.get_kpi_metrics()
        _report_dist = sim_result.get_distribution()
        _report_segments = sim_result.get_segments()
        _cfg_obj: CoinFlipConfig | None = st.session_state.get("config")
        if _cfg_obj is not None:
            _report_config = _cfg_obj.to_dict()
    elif loaded_summary is not None:
        _report_kpis = {
            k: float(v)
            for k, v in loaded_summary.items()
            if isinstance(v, (int, float)) and k != "threshold"
        }
        if loaded_distribution:
            _report_dist = {str(k): int(v) for k, v in loaded_distribution.items()}

    render_report_download(
        config=_report_config,
        kpi_metrics=_report_kpis,
        distribution=_report_dist,
        segments=_report_segments,
        insights=_report_insights,
    )


# ===========================================================================
# 5. AI ANALYSIS SECTION
# ===========================================================================

if has_any_result:
    render_ai_analysis(
        sim_result=sim_result,
        loaded_summary=loaded_summary,
        loaded_distribution=loaded_distribution,
        get_llm_client=_get_llm_client,
        use_case=_use_case,
        store=store,
    )


# ===========================================================================
# 6. PARAMETER SWEEP SECTION
# ===========================================================================

if has_any_result and has_config:
    # Use uploaded player data, or fall back to player data from loaded result
    _sweep_players: pl.DataFrame | None = st.session_state.get("player_data")
    if _sweep_players is None and sim_result is not None:
        _sweep_players = sim_result.player_results

    if _sweep_players is not None:
        st.markdown("---")
        from src.ui.sections.parameter_sweep import render_parameter_sweep

        render_parameter_sweep(
            players=_sweep_players,
            base_config=st.session_state.get("config"),
            simulator=CoinFlipSimulator(),
        )


# ===========================================================================
# Empty state placeholder (when no results yet)
# ===========================================================================

if not has_any_result:
    st.markdown("---")
    st.info(
        "No simulation results yet. "
        "Upload player data and config above, then run a simulation."
    )
