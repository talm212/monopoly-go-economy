"""Sidebar history section for viewing, loading, and comparing past runs.

Renders into ``st.sidebar`` and manages the run list, rename, load/delete
buttons, and the comparison selector.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import streamlit as st

from src.application.config_conversion import config_obj_to_display
from src.domain.models.coin_flip import CoinFlipConfig
from src.infrastructure.store.local_store import LocalSimulationStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_DISPLAY_RUNS = 50
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Helpers
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


def _clear_stale_ai_data() -> None:
    """Clear AI-related session state when simulation results change."""
    for key in (
        "ai_insights", "ai_chat_history", "optimizer_steps",
        "optimizer_best_config", "cached_csv_data",
    ):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_sidebar_history(store: LocalSimulationStore) -> None:
    """Render the full sidebar history section.

    Includes: run listing, rename text_input, load/delete buttons,
    and comparison selector.
    """
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

                    # Editable name — plain text_input, saves on rerun after Enter/blur
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
                            st.toast(f"Saved: {new_name}")
                        except Exception as exc:
                            st.error(f"Failed to save: {exc}")

                    load_col, delete_col = st.columns(2)
                    with load_col:
                        if st.button("Load", key=f"load_{run_id}", use_container_width=True):
                            run_config = run.get("config", {})
                            try:
                                if run_config:
                                    loaded_cfg = CoinFlipConfig.from_dict(run_config)
                                    st.session_state["config"] = loaded_cfg
                                    st.session_state["config_dict"] = config_obj_to_display(
                                        loaded_cfg
                                    )
                                    st.session_state["config_uploaded"] = True
                                    # Purge stale config editor widget keys
                                    for _k in list(st.session_state.keys()):
                                        if _k.startswith("cf_cfg_"):
                                            del st.session_state[_k]

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
                        if st.button("Delete", key=f"del_{run_id}", use_container_width=True):
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
