"""AI Analysis section rendering for the simulation dashboard.

Renders the Insights tab, Chat tab, and Optimizer tab.
Supports both fresh simulation results and loaded summaries from history.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl
import streamlit as st

from src.application.analyze_results import InsightsAnalyst
from src.application.chat_assistant import ChatAssistant
from src.application.optimize_config import ConfigOptimizer
from src.application.run_simulation import RunSimulationUseCase
from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult
from src.domain.models.insight import Insight
from src.domain.models.optimization import (
    OptimizationDirection,
    OptimizationStep,
    OptimizationTarget,
)
from src.infrastructure.store.local_store import LocalSimulationStore
from src.ui.async_helper import run_async
from src.ui.components.ai_chat_panel import render_ai_chat_panel
from src.ui.components.insight_cards import render_insight_card

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
# AI context builder
# ---------------------------------------------------------------------------


def _build_ai_context(
    sim_result: CoinFlipResult | None,
    loaded_summary: dict[str, Any] | None,
    loaded_distribution: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | float], dict[str, Any]]:
    """Build shared AI context from result or loaded summary.

    Returns:
        (config_dict, result_summary, distribution, kpi_metrics)
    """
    config_obj: CoinFlipConfig | None = st.session_state.get("config")
    config_dict_for_ai: dict[str, Any] = config_obj.to_dict() if config_obj is not None else {}

    if sim_result is not None:
        result_summary = sim_result.to_summary_dict()
        result_summary.update(sim_result.get_kpi_metrics())
        distribution: dict[str, Any] = sim_result.get_distribution()
        kpi_metrics = sim_result.get_kpi_metrics()

        # Add churn segment breakdown for AI context
        player_results = sim_result.player_results
        if "about_to_churn" in player_results.columns:
            churn_df = player_results.filter(pl.col("about_to_churn"))
            non_churn_df = player_results.filter(~pl.col("about_to_churn"))
            result_summary["churn_segment"] = {
                "churn_player_count": churn_df.height,
                "churn_mean_points": float(churn_df["total_points"].mean() or 0),
                "churn_median_points": float(churn_df["total_points"].median() or 0),
                "churn_total_points": float(churn_df["total_points"].sum() or 0),
                "non_churn_player_count": non_churn_df.height,
                "non_churn_mean_points": float(non_churn_df["total_points"].mean() or 0),
                "non_churn_median_points": float(non_churn_df["total_points"].median() or 0),
                "non_churn_total_points": float(non_churn_df["total_points"].sum() or 0),
            }
    elif loaded_summary:
        result_summary = loaded_summary
        distribution = {str(k): int(v) for k, v in (loaded_distribution or {}).items()}
        kpi_metrics = {
            "total_points": loaded_summary.get("total_points", 0),
            "mean_points_per_player": loaded_summary.get("mean_points_per_player", 0.0),
            "median_points_per_player": loaded_summary.get("median_points_per_player", 0.0),
            "pct_above_threshold": loaded_summary.get("pct_above_threshold", 0.0),
        }
    else:
        result_summary = {}
        distribution = {}
        kpi_metrics = {}

    return config_dict_for_ai, result_summary, distribution, kpi_metrics


# ---------------------------------------------------------------------------
# Stale data helper
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_ai_analysis(
    sim_result: CoinFlipResult | None,
    loaded_summary: dict[str, Any] | None,
    loaded_distribution: dict[str, Any] | None,
    get_llm_client: Any,
    use_case: RunSimulationUseCase,
    store: LocalSimulationStore,
) -> None:
    """Render the AI Analysis section (Insights, Chat, Optimizer tabs).

    Args:
        sim_result: Full simulation result (if a fresh simulation was run).
        loaded_summary: Summary dict from a loaded past run.
        loaded_distribution: Distribution dict from a loaded past run.
        get_llm_client: Callable that returns a cached LLM client.
        use_case: The RunSimulationUseCase for optimizer re-runs.
        store: The simulation store for saving optimizer results.
    """
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

    config_dict_for_ai, result_summary, distribution, kpi_metrics = _build_ai_context(
        sim_result, loaded_summary, loaded_distribution,
    )

    insights_tab, chat_tab, optimizer_tab = st.tabs(
        [
            "Insights",
            "Ask a Question",
            "Optimizer",
        ]
    )

    # --- Insights tab ---
    with insights_tab:
        _render_insights_tab(
            result_summary=result_summary,
            distribution=distribution,
            config_dict=config_dict_for_ai,
            kpi_metrics=kpi_metrics,
            get_llm_client=get_llm_client,
        )

    # --- Ask a Question tab ---
    with chat_tab:
        _render_chat_tab(
            result_summary=result_summary,
            distribution=distribution,
            config_dict=config_dict_for_ai,
            kpi_metrics=kpi_metrics,
            get_llm_client=get_llm_client,
        )

    # --- Optimizer tab ---
    with optimizer_tab:
        _render_optimizer_tab(
            use_case=use_case,
            store=store,
            get_llm_client=get_llm_client,
        )


# ---------------------------------------------------------------------------
# Private tab renderers
# ---------------------------------------------------------------------------


def _render_insights_tab(
    result_summary: dict[str, Any],
    distribution: dict[str, Any],
    config_dict: dict[str, Any],
    kpi_metrics: dict[str, Any],
    get_llm_client: Any,
) -> None:
    """Render the Insights tab."""
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
                        result_summary=result_summary,
                        distribution=distribution,
                        config=config_dict,
                        kpi_metrics=kpi_metrics,
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
            render_insight_card(insight)
    elif not generate_clicked:
        st.info("Click **Generate Insights** to analyze your simulation results with AI.")


def _render_chat_tab(
    result_summary: dict[str, Any],
    distribution: dict[str, Any],
    config_dict: dict[str, Any],
    kpi_metrics: dict[str, Any],
    get_llm_client: Any,
) -> None:
    """Render the Ask a Question (Chat) tab."""
    st.caption(
        "Chat with AI about your simulation results. Ask about trends, "
        "anomalies, or what-if scenarios."
    )
    try:
        llm_client_chat = get_llm_client()
        assistant = ChatAssistant(llm_client_chat)

        render_ai_chat_panel(
            assistant=assistant,
            result_summary=result_summary,
            distribution=distribution,
            config=config_dict,
            kpi_metrics=kpi_metrics,
        )
    except ValueError as exc:
        st.error(f"LLM configuration error: {exc}")
    except Exception:
        st.error("Failed to initialize chat assistant. Check your LLM configuration.")
        logger.exception("Chat assistant initialization failed")


def _render_optimizer_tab(
    use_case: RunSimulationUseCase,
    store: LocalSimulationStore,
    get_llm_client: Any,
) -> None:
    """Render the Optimizer tab."""
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
                res = use_case.execute_from_dataframe(players, cfg)
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
                from src.application.config_conversion import config_obj_to_display

                # Write optimized config to session state
                applied_config = CoinFlipConfig.from_dict(opt_best)
                st.session_state["config"] = applied_config
                st.session_state["config_dict"] = config_obj_to_display(applied_config)

                # Auto-run if player data exists
                player_data_apply: pl.DataFrame | None = st.session_state.get("player_data")
                if player_data_apply is not None:
                    new_result = use_case.execute_from_dataframe(
                        player_data_apply, applied_config
                    )
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
