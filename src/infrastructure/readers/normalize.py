"""Shared data normalization utilities for player DataFrames."""

from __future__ import annotations

import polars as pl


def normalize_churn_column(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize the about_to_churn column to boolean type.

    Handles:
    - Missing column: adds with default False
    - String column ("true"/"false", case-insensitive): converts to boolean
    - Already boolean: no-op
    """
    if "about_to_churn" not in df.columns:
        return df.with_columns(pl.lit(False).alias("about_to_churn"))

    if df["about_to_churn"].dtype == pl.Utf8:
        return df.with_columns(
            pl.col("about_to_churn").str.to_lowercase().eq("true").alias("about_to_churn")
        )

    return df
