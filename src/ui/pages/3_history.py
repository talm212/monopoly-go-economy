"""Simulation History page — browse, compare, and manage past simulation runs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import streamlit as st

from src.infrastructure.store.local_store import LocalSimulationStore
from src.ui.components.comparison_view import render_comparison_view

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
    feature = run.get("feature", "unknown")
    summary = run.get("result_summary", {})
    total_pts = summary.get("total_points", 0)
    try:
        return f"{created} | {feature} | {float(total_pts):,.0f} pts"
    except (ValueError, TypeError):
        return f"{created} | {feature}"


def _render_run_card(run: dict[str, Any]) -> None:
    """Render a compact summary card for a single run."""
    created = _format_timestamp(run.get("created_at", ""))
    feature = run.get("feature", "unknown")
    summary = run.get("result_summary", {})
    config = run.get("config", {})

    col_date, col_feature, col_points, col_interactions = st.columns(4)
    with col_date:
        st.caption("Date")
        st.write(created)
    with col_feature:
        st.caption("Feature")
        st.write(feature)
    with col_points:
        st.caption("Total Points")
        st.write(f"{summary.get('total_points', 0):,.0f}")
    with col_interactions:
        st.caption("Total Interactions")
        st.write(f"{summary.get('total_interactions', 0):,}")

    with st.expander("Configuration", expanded=False):
        st.json(config)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.header("Simulation History")
st.markdown(
    "Browse past simulation runs, compare results side-by-side, "
    "and manage your simulation history."
)

store = LocalSimulationStore()

# ---- Feature filter -------------------------------------------------------

# Get unique features from stored runs
all_runs = store.list_runs(limit=100)
available_features = sorted({r.get("feature", "unknown") for r in all_runs})
feature_options = ["All"] + available_features
feature_filter = st.selectbox("Filter by feature", options=feature_options, index=0)

selected_feature: str | None = None if feature_filter == "All" else feature_filter

# ---- Load runs ------------------------------------------------------------

runs = store.list_runs(feature=selected_feature, limit=_MAX_DISPLAY_RUNS)

if not runs:
    st.info(
        "No simulation runs found. "
        "Run a simulation from the **Run Simulation** page to see history here."
    )
    st.stop()

st.write(f"**{len(runs)}** run(s) found.")

# ---- Run list -------------------------------------------------------------

st.subheader("Past Runs")

for run in runs:
    with st.container(border=True):
        _render_run_card(run)

st.markdown("---")

# ---- Comparison selector --------------------------------------------------

st.subheader("Compare Two Runs")
st.markdown("Select two runs below to see a side-by-side comparison.")

run_labels = {run["run_id"]: _format_run_label(run) for run in runs}
run_ids = list(run_labels.keys())

if len(runs) < 2:
    st.info("Need at least 2 runs to compare. Run more simulations first.")
else:
    col_select_a, col_select_b = st.columns(2)

    with col_select_a:
        selected_a = st.selectbox(
            "Run A",
            options=run_ids,
            format_func=lambda x: run_labels.get(x, x),
            index=0,
            key="compare_run_a",
        )

    with col_select_b:
        default_b_index = 1 if len(run_ids) > 1 else 0
        selected_b = st.selectbox(
            "Run B",
            options=run_ids,
            format_func=lambda x: run_labels.get(x, x),
            index=default_b_index,
            key="compare_run_b",
        )

    if selected_a and selected_b:
        if selected_a == selected_b:
            st.warning("Please select two different runs for comparison.")
        else:
            compare_clicked = st.button("Compare", type="primary", use_container_width=True)
            if compare_clicked:
                run_a = store.get_run(selected_a)
                run_b = store.get_run(selected_b)

                label_a = _format_run_label(run_a)
                label_b = _format_run_label(run_b)

                render_comparison_view(
                    run_a=run_a,
                    run_b=run_b,
                    label_a=label_a,
                    label_b=label_b,
                )

st.markdown("---")

# ---- Delete runs -----------------------------------------------------------

st.subheader("Manage History")

with st.expander("Delete Runs", expanded=False):
    st.warning("Deleted runs cannot be recovered.")

    runs_to_delete = st.multiselect(
        "Select runs to delete",
        options=run_ids,
        format_func=lambda x: run_labels.get(x, x),
        key="delete_runs_select",
    )

    if runs_to_delete:
        delete_clicked = st.button(
            f"Delete {len(runs_to_delete)} run(s)",
            type="secondary",
        )
        if delete_clicked:
            deleted_count = 0
            for run_id in runs_to_delete:
                try:
                    store.delete_run(run_id)
                    deleted_count += 1
                except FileNotFoundError:
                    logger.warning("Run %s already deleted", run_id)

            st.success(f"Deleted {deleted_count} run(s).")
            logger.info("Deleted %d simulation runs", deleted_count)
            st.rerun()
