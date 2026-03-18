"""Upload & Configure page — upload player/config CSVs and edit parameters."""
from __future__ import annotations

import logging
from typing import Any

import polars as pl
import streamlit as st

from src.domain.models.coin_flip import CoinFlipConfig
from src.infrastructure.readers.local_reader import LocalDataReader
from src.ui.components.config_editor import render_config_editor
from src.ui.components.upload_widget import render_upload_widget

logger = logging.getLogger(__name__)

_reader = LocalDataReader()


# ---------------------------------------------------------------------------
# Helper: parse config CSV DataFrame into raw string dict
# ---------------------------------------------------------------------------


def _config_df_to_raw_dict(df: pl.DataFrame) -> dict[str, str]:
    """Convert a config CSV DataFrame (Input, Value columns) to a raw string dict.

    The returned dict preserves the original string representations (e.g. '60%')
    so it can be fed to ``CoinFlipConfig.from_csv_dict`` or the config editor.
    """
    raw: dict[str, str] = {}
    for row in df.iter_rows(named=True):
        raw[str(row["Input"])] = str(row["Value"])
    return raw


def _raw_dict_to_display(raw: dict[str, str]) -> dict[str, Any]:
    """Convert raw CSV string dict to display-friendly types for the editor.

    - Percentage strings ('60%') stay as-is (the editor has a slider for them).
    - Pure integer strings become ``int``.
    - Decimal strings become ``float``.
    """
    display: dict[str, Any] = {}
    for key, value in raw.items():
        if value.endswith("%"):
            display[key] = value  # keep as percentage string
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
    """Convert the editor's display dict back to raw string form for from_csv_dict."""
    raw: dict[str, str] = {}
    for key, value in display.items():
        if isinstance(value, str):
            raw[key] = value
        elif isinstance(value, float) and not isinstance(value, bool):
            # Avoid trailing .0 for whole numbers
            if value == int(value):
                raw[key] = str(int(value))
            else:
                raw[key] = str(value)
        else:
            raw[key] = str(value)
    return raw


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.header("Upload & Configure")
st.markdown(
    "Upload your player data and configuration CSVs, then fine-tune "
    "simulation parameters before running."
)

# ---- Section 1: Player data upload ----------------------------------------

st.subheader("1. Player Data")

player_df = render_upload_widget(
    label="Upload player CSV (user_id, rolls_sink, avg_multiplier, about_to_churn)",
    accepted_types=["csv"],
    key="player_upload",
)

if player_df is not None:
    # Validate using LocalDataReader
    validation_errors = _reader.validate_players(player_df)
    if validation_errors:
        for err in validation_errors:
            st.error(err)
        logger.warning("Player data validation failed: %s", validation_errors)
    else:
        st.success("Player data is valid.")
        st.metric("Total players", f"{player_df.height:,}")

        with st.expander("Preview (first 10 rows)", expanded=False):
            st.dataframe(player_df.head(10), use_container_width=True)

        # Normalise about_to_churn column before storing
        if "about_to_churn" not in player_df.columns:
            player_df = player_df.with_columns(pl.lit(False).alias("about_to_churn"))
        elif player_df["about_to_churn"].dtype == pl.Utf8:
            player_df = player_df.with_columns(
                pl.col("about_to_churn")
                .str.to_lowercase()
                .map_elements(
                    lambda v: v == "true" if v is not None else False,
                    return_dtype=pl.Boolean,
                )
                .alias("about_to_churn")
            )

        st.session_state["player_data"] = player_df
        logger.info("Player data stored in session state (%d rows)", player_df.height)
else:
    st.info("Please upload a player CSV to get started.")

st.markdown("---")

# ---- Section 2: Config CSV upload -----------------------------------------

st.subheader("2. Simulation Config")

config_df = render_upload_widget(
    label="Upload config CSV (Input, Value columns)",
    accepted_types=["csv"],
    key="config_upload",
)

if config_df is not None:
    try:
        raw_config = _config_df_to_raw_dict(config_df)
        display_config = _raw_dict_to_display(raw_config)

        st.success(f"Parsed **{len(raw_config)}** config parameters.")

        with st.expander("Raw config table", expanded=False):
            st.dataframe(config_df, use_container_width=True)

        # Store the display dict so the editor can use it
        st.session_state["config_dict"] = display_config
        logger.info("Config dict stored in session state (%d keys)", len(display_config))
    except Exception:
        logger.exception("Failed to parse config CSV")
        st.error(
            "Failed to parse the config CSV. "
            "Ensure it has 'Input' and 'Value' columns."
        )
else:
    if "config_dict" not in st.session_state:
        st.info("Please upload a config CSV, or use the default editor below.")

st.markdown("---")

# ---- Section 3: Config editor ---------------------------------------------

st.subheader("3. Edit Parameters")

if "config_dict" in st.session_state:
    current_config = st.session_state["config_dict"]
    edited_config = render_config_editor(current_config, key_prefix="cfg")

    # Persist edited values back to session state
    st.session_state["config_dict"] = edited_config

    # Build CoinFlipConfig from edited values
    try:
        raw_for_model = _display_dict_to_raw(edited_config)
        coin_flip_config = CoinFlipConfig.from_csv_dict(raw_for_model)
        coin_flip_config.validate()

        st.session_state["config"] = coin_flip_config
        logger.info("CoinFlipConfig built and stored in session state")
    except (KeyError, ValueError) as exc:
        st.error(f"Config validation error: {exc}")
        logger.warning("CoinFlipConfig validation failed: %s", exc)
        # Remove stale config so downstream pages don't use invalid data
        st.session_state.pop("config", None)
else:
    st.info(
        "Upload a config CSV above to populate the editor, "
        "or the editor will appear once config data is available."
    )

st.markdown("---")

# ---- Section 4: Readiness summary -----------------------------------------

st.subheader("Status")

has_players = "player_data" in st.session_state
has_config = "config" in st.session_state

col1, col2 = st.columns(2)
with col1:
    if has_players:
        row_count = st.session_state["player_data"].height
        st.success(f"Player data: {row_count:,} rows")
    else:
        st.warning("Player data: not uploaded")

with col2:
    if has_config:
        cfg = st.session_state["config"]
        st.success(f"Config: {cfg.max_successes} flip depths")
    else:
        st.warning("Config: not set")

if has_players and has_config:
    st.success("Ready to simulate! Navigate to **Run Simulation** to proceed.")
elif not has_players and not has_config:
    st.info("Upload both player data and config to get started.")
