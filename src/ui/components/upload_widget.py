"""Reusable file upload widget that converts CSV uploads to Polars DataFrames."""

from __future__ import annotations

import io
import logging

import polars as pl
import streamlit as st

logger = logging.getLogger(__name__)


def render_upload_widget(
    label: str,
    accepted_types: list[str],
    key: str,
) -> pl.DataFrame | None:
    """Render a file upload widget and return the uploaded data as a Polars DataFrame.

    Args:
        label: Display label for the upload widget.
        accepted_types: List of accepted file extensions (e.g. ["csv"]).
        key: Unique Streamlit widget key to avoid duplicate widget IDs.

    Returns:
        A Polars DataFrame if a file was successfully uploaded and parsed,
        or None if no file has been uploaded yet.
    """
    uploaded_file = st.file_uploader(label, type=accepted_types, key=key)

    if uploaded_file is None:
        return None

    try:
        raw_bytes = uploaded_file.getvalue()
        df = pl.read_csv(io.BytesIO(raw_bytes))
    except Exception:
        logger.exception("Failed to parse uploaded file as CSV")
        st.error("Failed to parse the uploaded file. Please ensure it is a valid CSV.")
        return None

    row_count = df.height
    column_names = df.columns

    st.success(f"Loaded **{row_count:,}** rows across **{len(column_names)}** columns.")
    st.caption(f"Columns: {', '.join(column_names)}")
    st.dataframe(df.head(5), use_container_width=True)

    logger.info("Uploaded file parsed: %d rows, columns=%s", row_count, column_names)
    return df
