"""Local CSV writer for simulation results using Polars.

Provides a reusable data I/O layer that writes Polars DataFrames
to local CSV files.
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


class LocalDataWriter:
    """Writes simulation results to local CSV files using Polars."""

    def write_results(self, df: pl.DataFrame, destination: str) -> None:
        """Write a Polars DataFrame to CSV.

        Creates parent directories if they do not exist.

        Args:
            df: Polars DataFrame to write.
            destination: File path for the output CSV.
        """
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Writing %d rows to %s", len(df), destination)
        df.write_csv(destination)
        logger.info("Successfully wrote results to %s", destination)
