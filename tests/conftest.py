"""Shared test fixtures for the monopoly-go-economy test suite.

All fixtures here are available to every test file without explicit import.
Randomness is seeded for deterministic, reproducible test results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest


# ---------------------------------------------------------------------------
# Seeded RNG
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_rng() -> np.random.Generator:
    """NumPy random generator with fixed seed for reproducible tests."""
    return np.random.default_rng(seed=42)


# ---------------------------------------------------------------------------
# Sample player data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_players_df() -> pl.DataFrame:
    """Small player DataFrame matching input_table.csv schema.

    10 players with varying rolls_sink, avg_multiplier, and churn status.
    """
    return pl.DataFrame(
        {
            "user_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "rolls_sink": [100, 200, 50, 500, 1000, 150, 300, 80, 600, 250],
            "avg_multiplier": [10, 20, 5, 50, 100, 10, 30, 10, 50, 25],
            "about_to_churn": [
                False,
                False,
                True,
                False,
                False,
                True,
                False,
                False,
                True,
                False,
            ],
        }
    )


@pytest.fixture
def large_players_df() -> pl.DataFrame:
    """1000-player DataFrame for integration tests."""
    rng = np.random.default_rng(seed=99)
    n = 1000
    return pl.DataFrame(
        {
            "user_id": list(range(1, n + 1)),
            "rolls_sink": rng.integers(50, 2000, size=n).tolist(),
            "avg_multiplier": rng.choice([1, 2, 5, 10, 20, 50], size=n).tolist(),
            "about_to_churn": rng.choice([True, False], size=n, p=[0.1, 0.9]).tolist(),
        }
    )


# ---------------------------------------------------------------------------
# Sample config
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config_dict() -> dict[str, Any]:
    """Coin flip config matching config_table.csv values."""
    return {
        "max_successes": 5,
        "probabilities": [0.60, 0.50, 0.50, 0.50, 0.50],
        "point_values": [1.0, 2.0, 4.0, 8.0, 16.0],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


# ---------------------------------------------------------------------------
# Temporary file helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_input_csv(tmp_path: Path) -> str:
    """Write a small player CSV to tmp_path and return the path."""
    path = tmp_path / "input_table.csv"
    df = pl.DataFrame(
        {
            "user_id": [1, 2, 3],
            "rolls_sink": [100, 200, 50],
            "avg_multiplier": [10, 20, 5],
            "about_to_churn": [False, False, True],
        }
    )
    df.write_csv(str(path))
    return str(path)


@pytest.fixture
def sample_config_csv(tmp_path: Path) -> str:
    """Write a config CSV to tmp_path and return the path."""
    path = tmp_path / "config_table.csv"
    df = pl.DataFrame(
        {
            "Input": [
                "p_success_1",
                "p_success_2",
                "p_success_3",
                "p_success_4",
                "p_success_5",
                "max_successes",
                "points_success_1",
                "points_success_2",
                "points_success_3",
                "points_success_4",
                "points_success_5",
            ],
            "Value": [
                "60%",
                "50%",
                "50%",
                "50%",
                "50%",
                "5",
                "1",
                "2",
                "4",
                "8",
                "16",
            ],
        }
    )
    df.write_csv(str(path))
    return str(path)
