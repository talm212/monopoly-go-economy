"""Reusable dynamic configuration editor that renders form fields from a dict."""

from __future__ import annotations

import logging
import re
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

_PERCENTAGE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)%$")

# Help texts for known config parameters
_PARAM_HELP: dict[str, str] = {
    "p_success_1": "Probability of landing heads on flip 1. Higher = more players advance.",
    "p_success_2": "Probability of landing heads on flip 2 (after passing flip 1).",
    "p_success_3": "Probability of landing heads on flip 3 (after passing flips 1-2).",
    "p_success_4": "Probability of landing heads on flip 4 (after passing flips 1-3).",
    "p_success_5": "Probability of landing heads on flip 5 (after passing flips 1-4).",
    "points_success_1": "Points awarded for reaching depth 1 (first successful flip).",
    "points_success_2": "Points awarded for reaching depth 2 (cumulative with depth 1).",
    "points_success_3": "Points awarded for reaching depth 3 (cumulative with depths 1-2).",
    "points_success_4": "Points awarded for reaching depth 4 (cumulative with depths 1-3).",
    "points_success_5": "Points awarded for reaching depth 5 (jackpot — cumulative with all).",
    "max_successes": "Maximum flip chain depth. Determines how many consecutive flips a player can attempt per interaction.",
    "churn_boost_multiplier": "Multiplier applied to flip probabilities for about-to-churn players. E.g., 1.3 = 30% boost, capped at 100%.",
    "reward_threshold": "Point threshold for the '% Above Threshold' KPI. Players with total_points above this value are counted.",
}


def _is_percentage(value: Any) -> bool:
    """Check whether a value is a percentage string like '60%'."""
    return isinstance(value, str) and _PERCENTAGE_PATTERN.match(value) is not None


def _parse_percentage(value: str) -> float:
    """Extract the numeric portion of a percentage string."""
    match = _PERCENTAGE_PATTERN.match(value)
    if match is None:
        return 0.0
    return float(match.group(1))


def render_config_editor(
    config: dict[str, Any],
    key_prefix: str,
) -> dict[str, Any]:
    """Render editable form fields for each entry in the config dict.

    Automatically selects the appropriate Streamlit widget based on value type:
    - ``bool`` -> checkbox
    - ``int`` -> integer number input
    - ``float`` -> float number input
    - percentage string (e.g. ``"60%"``) -> slider (0-100)
    - other ``str`` -> text input

    Args:
        config: Dictionary of configuration key-value pairs.
        key_prefix: Prefix added to Streamlit widget keys to ensure uniqueness.

    Returns:
        A new dictionary with the same keys and user-edited values.
    """
    edited: dict[str, Any] = {}

    for param_name, value in config.items():
        widget_key = f"{key_prefix}_{param_name}"
        display_label = param_name.replace("_", " ").title()
        param_help = _PARAM_HELP.get(param_name)

        # Order matters: check bool before int (bool is a subclass of int in Python)
        if isinstance(value, bool):
            edited[param_name] = st.checkbox(display_label, value=value, key=widget_key, help=param_help)

        elif _is_percentage(value):
            pct_value = _parse_percentage(value)
            slider_result: float = st.slider(
                display_label,
                min_value=0.0,
                max_value=100.0,
                value=pct_value,
                step=0.5,
                format="%.1f%%",
                key=widget_key,
                help=param_help,
            )
            edited[param_name] = f"{slider_result}%"

        elif isinstance(value, int):
            edited[param_name] = int(
                st.number_input(
                    display_label,
                    value=value,
                    step=1,
                    key=widget_key,
                    help=param_help,
                )
            )

        elif isinstance(value, float):
            edited[param_name] = float(
                st.number_input(
                    display_label,
                    value=value,
                    step=0.01,
                    format="%.4f",
                    key=widget_key,
                    help=param_help,
                )
            )

        elif isinstance(value, str):
            edited[param_name] = st.text_input(display_label, value=value, key=widget_key, help=param_help)

        else:
            # Fallback: render as text and preserve original type
            logger.warning(
                "Unsupported config type %s for key '%s'; rendering as text",
                type(value).__name__,
                param_name,
            )
            edited[param_name] = st.text_input(display_label, value=str(value), key=widget_key)

    return edited
