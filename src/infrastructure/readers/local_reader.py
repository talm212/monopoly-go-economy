"""Local CSV reader for player data and simulation config using Polars.

Provides a reusable data I/O layer that reads CSV files into Polars
DataFrames (players) or plain dicts (config), with validation and
type parsing.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from src.domain.errors import InvalidPlayerDataError
from src.infrastructure.readers.normalize import normalize_churn_column

logger = logging.getLogger(__name__)

_REQUIRED_PLAYER_COLUMNS: tuple[str, ...] = ("user_id", "rolls_sink", "avg_multiplier")


class LocalDataReader:
    """Reads player data and config from local CSV files using Polars."""

    def read_players(self, source: str) -> pl.DataFrame:
        """Read player CSV. Validates required columns exist and data is clean.

        Args:
            source: Path to the player CSV file.

        Returns:
            Polars DataFrame with columns user_id, rolls_sink,
            avg_multiplier, and about_to_churn (boolean).

        Raises:
            FileNotFoundError: If the source file does not exist.
            InvalidPlayerDataError: If required columns are missing or data is invalid.
        """
        logger.info("Reading player data from %s", source)
        df = pl.read_csv(source)

        # Normalise the about_to_churn column (vectorized, no Python lambdas)
        df = normalize_churn_column(df)

        # Validate and raise on errors
        errors = self.validate_players(df)
        if errors:
            msg = "Player data validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(msg)
            raise InvalidPlayerDataError(msg)

        logger.info("Successfully read %d players from %s", len(df), source)
        return df

    def read_config(self, source: str) -> dict[str, Any]:
        """Read config CSV (Input/Value format) into a dict.

        Parses percentage strings (e.g., '60%' to 0.60) and numeric
        strings to int or float as appropriate.

        Args:
            source: Path to the config CSV file.

        Returns:
            Dictionary mapping config key names to parsed values.

        Raises:
            FileNotFoundError: If the source file does not exist.
        """
        logger.info("Reading config from %s", source)
        df = pl.read_csv(source)

        config: dict[str, Any] = {}
        for row in df.iter_rows(named=True):
            key = row["Input"]
            raw_value: str = str(row["Value"])
            config[key] = self._parse_config_value(raw_value)

        logger.info("Parsed %d config entries from %s", len(config), source)
        return config

    def validate_players(self, df: pl.DataFrame) -> list[str]:
        """Validate player DataFrame. Returns list of errors (empty = valid).

        Checks:
        - Required columns exist: user_id, rolls_sink, avg_multiplier
        - No null values in required columns

        Args:
            df: Polars DataFrame to validate.

        Returns:
            List of human-readable error messages. Empty list means valid.
        """
        errors: list[str] = []

        # Check required columns
        for col in _REQUIRED_PLAYER_COLUMNS:
            if col not in df.columns:
                errors.append(f"Missing required column: '{col}'")

        # Check for null values in present required columns
        for col in _REQUIRED_PLAYER_COLUMNS:
            if col in df.columns:
                null_count = df[col].null_count()
                if null_count > 0:
                    errors.append(f"Column '{col}' contains {null_count} null value(s)")

        return errors

    @staticmethod
    def _parse_config_value(raw: str) -> int | float:
        """Parse a single config value string into a typed Python value.

        Rules:
        - '60%' -> 0.60 (float)
        - '5'   -> 5 (int)
        - '2.5' -> 2.5 (float)
        """
        if raw.endswith("%"):
            return float(raw.rstrip("%")) / 100.0

        # Try int first, then float
        try:
            return int(raw)
        except ValueError:
            return float(raw)
