"""Smoke tests to verify fixtures and test infrastructure work correctly."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest


@pytest.mark.unit
class TestFixtures:
    """Verify all shared fixtures are accessible and well-formed."""

    def test_seeded_rng_is_deterministic(self, seeded_rng: np.random.Generator) -> None:
        result = seeded_rng.random(5)
        expected = np.random.default_rng(42).random(5)
        np.testing.assert_array_equal(result, expected)

    def test_sample_players_df_schema(self, sample_players_df: pl.DataFrame) -> None:
        assert sample_players_df.shape[0] == 10
        assert set(sample_players_df.columns) == {
            "user_id", "rolls_sink", "avg_multiplier", "about_to_churn",
        }

    def test_sample_players_df_has_churn_players(self, sample_players_df: pl.DataFrame) -> None:
        churn_count = sample_players_df.filter(pl.col("about_to_churn")).shape[0]
        assert churn_count > 0, "Fixture must include churn players for testing"

    def test_large_players_df_size(self, large_players_df: pl.DataFrame) -> None:
        assert large_players_df.shape[0] == 1000

    def test_sample_config_dict_structure(self, sample_config_dict: dict[str, Any]) -> None:
        assert sample_config_dict["max_successes"] == 5
        assert len(sample_config_dict["probabilities"]) == 5
        assert len(sample_config_dict["point_values"]) == 5
        assert sample_config_dict["churn_boost_multiplier"] == 1.3

    def test_sample_input_csv_readable(self, sample_input_csv: str) -> None:
        df = pl.read_csv(sample_input_csv)
        assert df.shape[0] == 3
        assert "user_id" in df.columns

    def test_sample_config_csv_readable(self, sample_config_csv: str) -> None:
        df = pl.read_csv(sample_config_csv)
        assert df.shape[0] == 11
        assert "Input" in df.columns
        assert "Value" in df.columns
