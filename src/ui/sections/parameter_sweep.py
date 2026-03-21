"""Parameter Sweep UI section for the Economy Simulator dashboard.

Renders controls to sweep one config parameter across a range and compare
KPI results via line chart and data table.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl
import streamlit as st

from src.application.parameter_sweep import ParameterSweep, SweepResult
from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.simulators.coin_flip import CoinFlipSimulator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sweepable parameter definitions
# ---------------------------------------------------------------------------

# Maps display name -> (param_name for sweep, min, max, default_start, default_end)
_SWEEPABLE_PARAMS: dict[str, dict[str, Any]] = {}


def _build_sweepable_params(max_successes: int) -> dict[str, dict[str, Any]]:
    """Build sweepable parameter metadata based on config depth."""
    params: dict[str, dict[str, Any]] = {}
    for i in range(max_successes):
        params[f"p_success_{i + 1}"] = {
            "param_name": f"probabilities.{i}",
            "min": 0.0,
            "max": 1.0,
            "default_start": 0.1,
            "default_end": 0.9,
            "format": "%.2f",
            "help": f"Probability of success at flip depth {i + 1}",
        }
    for i in range(max_successes):
        params[f"points_success_{i + 1}"] = {
            "param_name": f"point_values.{i}",
            "min": 0.0,
            "max": 100.0,
            "default_start": 1.0,
            "default_end": 20.0,
            "format": "%.1f",
            "help": f"Points awarded at flip depth {i + 1}",
        }
    params["reward_threshold"] = {
        "param_name": "reward_threshold",
        "min": 0.0,
        "max": 10000.0,
        "default_start": 50.0,
        "default_end": 500.0,
        "format": "%.0f",
        "help": "Point threshold for KPI reporting",
    }
    return params


# ---------------------------------------------------------------------------
# KPI display names for chart Y-axis
# ---------------------------------------------------------------------------

_KPI_DISPLAY_NAMES: dict[str, str] = {
    "mean_points_per_player": "Mean Points / Player",
    "median_points_per_player": "Median Points / Player",
    "total_points": "Total Points",
    "pct_above_threshold": "% Above Threshold",
}


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def render_parameter_sweep(
    players: pl.DataFrame | None,
    base_config: CoinFlipConfig | None,
    simulator: CoinFlipSimulator,
) -> None:
    """Render the Parameter Sweep section.

    Args:
        players: Player DataFrame, or None if not uploaded.
        base_config: Current CoinFlipConfig, or None if not configured.
        simulator: CoinFlipSimulator instance for running simulations.
    """
    with st.expander("Parameter Sweep", expanded=False):
        st.caption(
            "Sweep one config parameter across a range of values to see how it affects KPIs. "
            "For example, vary p_success_1 from 30% to 80% to find the sweet spot. "
            "Each step runs a full simulation — results appear as a line chart and data table."
        )
        if players is None or base_config is None:
            st.info("Upload player data and config to use parameter sweep.")
            return

        config_dict = base_config.to_dict()
        max_successes = base_config.max_successes
        sweepable = _build_sweepable_params(max_successes)

        # --- Check for AI-suggested prefill ---
        prefill: dict[str, Any] | None = st.session_state.pop("sweep_prefill", None)
        if prefill is not None:
            prefill_param = prefill.get("parameter", "")
            if prefill_param in sweepable:
                st.success(
                    f"Pre-filled from AI insight: **{prefill_param}** "
                    f"{prefill['start']} \u2192 {prefill['end']} "
                    f"({prefill['steps']} steps)"
                )

        # --- Parameter selector ---
        param_display_names = list(sweepable.keys())
        default_param_idx = 0
        if prefill and prefill.get("parameter") in param_display_names:
            default_param_idx = param_display_names.index(prefill["parameter"])

        selected_display = st.selectbox(
            "Parameter to sweep",
            options=param_display_names,
            index=default_param_idx,
            key="sweep_param_select",
            help="Choose which configuration parameter to vary across the sweep.",
        )

        if selected_display is None:
            return

        param_meta = sweepable[selected_display]
        param_name = param_meta["param_name"]

        # Use prefill values if available and matching the selected param
        _prefill_start = param_meta["default_start"]
        _prefill_end = param_meta["default_end"]
        _prefill_steps = 5
        if prefill and prefill.get("parameter") == selected_display:
            _prefill_start = float(prefill["start"])
            _prefill_end = float(prefill["end"])
            _prefill_steps = int(prefill["steps"])

        # --- Range inputs ---
        range_cols = st.columns(3)
        with range_cols[0]:
            start_val = st.number_input(
                "Start value",
                min_value=param_meta["min"],
                max_value=param_meta["max"],
                value=_prefill_start,
                format=param_meta["format"],
                key="sweep_start",
                help="Starting value for the parameter sweep range.",
            )
        with range_cols[1]:
            end_val = st.number_input(
                "End value",
                min_value=param_meta["min"],
                max_value=param_meta["max"],
                value=_prefill_end,
                format=param_meta["format"],
                key="sweep_end",
                help="Ending value for the parameter sweep range.",
            )
        with range_cols[2]:
            step_count = st.number_input(
                "Number of steps",
                min_value=2,
                max_value=50,
                value=_prefill_steps,
                step=1,
                key="sweep_steps",
                help="Number of evenly spaced values between start and end.",
            )

        # Validate range
        if start_val >= end_val:
            st.warning("Start value must be less than end value.")
            return

        # Compute sweep values
        step_size = (end_val - start_val) / (step_count - 1)
        sweep_values = [start_val + i * step_size for i in range(step_count)]

        # --- Seed ---
        sweep_seed = st.number_input(
            "Sweep seed (optional)",
            min_value=0,
            max_value=2**31 - 1,
            value=None,
            step=1,
            placeholder="Random",
            key="sweep_seed",
            help="Seeds the RNG for reproducible sweep results.",
        )
        seed: int | None = int(sweep_seed) if sweep_seed is not None else None

        # --- KPI selector ---
        kpi_options = list(_KPI_DISPLAY_NAMES.keys())
        kpi_display = list(_KPI_DISPLAY_NAMES.values())
        selected_kpi_display = st.selectbox(
            "KPI to chart",
            options=kpi_display,
            index=0,
            key="sweep_kpi_select",
            help="Select which KPI to plot on the Y-axis.",
        )
        # Map display name back to key
        selected_kpi = kpi_options[kpi_display.index(selected_kpi_display)]

        # --- Run Sweep button ---
        run_sweep = st.button(
            "Run Sweep",
            type="primary",
            key="sweep_run",
            use_container_width=True,
            help="Runs one simulation per step, collecting KPI metrics at each value.",
        )

        if run_sweep:
            sweep_use_case = ParameterSweep(simulator)
            try:
                with st.spinner(
                    f"Running sweep: {selected_display} from "
                    f"{start_val} to {end_val} ({step_count} steps)..."
                ):
                    result = sweep_use_case.run(
                        players=players,
                        base_config=config_dict,
                        param_name=param_name,
                        values=sweep_values,
                        seed=seed,
                    )
                st.session_state["sweep_result"] = result
                st.session_state["sweep_kpi"] = selected_kpi
                st.session_state["sweep_param_display"] = selected_display
                st.toast(
                    f"Sweep complete: {len(result.sweep_points)} configurations tested."
                )
            except Exception:
                logger.exception("Parameter sweep failed")
                st.error("Parameter sweep failed. Check your configuration.")

        # --- Display results ---
        sweep_result: SweepResult | None = st.session_state.get("sweep_result")
        if sweep_result is not None:
            _render_sweep_results(
                sweep_result,
                st.session_state.get("sweep_kpi", "mean_points_per_player"),
                st.session_state.get("sweep_param_display", "parameter"),
            )


def _render_sweep_results(
    result: SweepResult,
    selected_kpi: str,
    param_display: str,
) -> None:
    """Render sweep results: chart, table, and download button."""
    df = result.to_dataframe()

    if df.height == 0:
        st.warning("No sweep results to display.")
        return

    st.markdown("---")
    st.subheader("Sweep Results")

    # --- Line chart ---
    kpi_display_name = _KPI_DISPLAY_NAMES.get(selected_kpi, selected_kpi)

    # Build chart DataFrame with renamed columns for display
    chart_df = df.select([
        pl.col("param_value").alias(param_display),
        pl.col(selected_kpi).alias(kpi_display_name),
    ])

    st.line_chart(
        chart_df.to_pandas(),
        x=param_display,
        y=kpi_display_name,
    )

    # --- Results table ---
    st.markdown("#### All Sweep Points")

    # Rename columns for display
    display_df = df.rename({
        "param_value": param_display,
        **{k: v for k, v in _KPI_DISPLAY_NAMES.items() if k in df.columns},
    })
    st.dataframe(display_df, use_container_width=True)

    # --- Download button ---
    csv_data = df.write_csv()
    st.download_button(
        label="Download Sweep Results (CSV)",
        data=csv_data,
        file_name="parameter_sweep_results.csv",
        mime="text/csv",
        key="sweep_download",
        help="Download all sweep points with every KPI value as a CSV file.",
    )
