"""Config format conversion helpers.

Reusable functions for converting between the three config representations:
1. CSV dict  (str keys, str values -- as parsed from CSV file)
2. Display dict  (str keys, mixed values -- as shown in the Streamlit editor)
3. Domain model  (e.g., CoinFlipConfig with typed tuples)

These are generic enough for any feature's config CSV processing.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from src.domain.models.coin_flip import CoinFlipConfig


def config_df_to_raw_dict(df: pl.DataFrame) -> dict[str, str]:
    """Convert a config CSV DataFrame (Input, Value columns) to a raw string dict."""
    raw: dict[str, str] = {}
    for row in df.iter_rows(named=True):
        raw[str(row["Input"])] = str(row["Value"])
    return raw


def raw_dict_to_display(raw: dict[str, str]) -> dict[str, Any]:
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


def display_dict_to_raw(display: dict[str, Any]) -> dict[str, str]:
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


def config_obj_to_display(config: CoinFlipConfig) -> dict[str, Any]:
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
