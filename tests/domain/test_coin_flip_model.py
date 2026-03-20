"""Tests for CoinFlipConfig.validate() edge cases and CoinFlipResult.get_kpi_metrics().

Covers zero-coverage paths:
- validate() rejects NaN probability
- validate() rejects inf point value
- get_kpi_metrics() with zero-row player_results DataFrame
"""

from __future__ import annotations

import math

import polars as pl
import pytest

from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult

# ---------------------------------------------------------------------------
# CoinFlipConfig.validate() — NaN and inf edge cases
# ---------------------------------------------------------------------------


class TestValidateNanInf:
    """Verify validate() rejects non-finite values (NaN, inf)."""

    def test_nan_probability_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, float("nan")),
            point_values=(1.0, 2.0),
        )
        with pytest.raises(ValueError, match="probability at index 1"):
            config.validate()

    def test_nan_first_probability_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(float("nan"),),
            point_values=(1.0,),
        )
        with pytest.raises(ValueError, match="probability at index 0"):
            config.validate()

    def test_inf_point_value_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.0, float("inf")),
        )
        with pytest.raises(ValueError, match="point_values at index 1"):
            config.validate()

    def test_negative_inf_point_value_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.5,),
            point_values=(float("-inf"),),
        )
        with pytest.raises(ValueError, match="point_values at index 0"):
            config.validate()

    def test_inf_probability_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(float("inf"),),
            point_values=(1.0,),
        )
        with pytest.raises(ValueError, match="probability at index 0"):
            config.validate()

    def test_nan_point_value_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.5,),
            point_values=(float("nan"),),
        )
        with pytest.raises(ValueError, match="point_values at index 0"):
            config.validate()


# ---------------------------------------------------------------------------
# CoinFlipResult.get_kpi_metrics() — empty DataFrame
# ---------------------------------------------------------------------------


class TestGetKpiMetricsEmpty:
    """Verify get_kpi_metrics() handles zero-row DataFrames gracefully."""

    def test_zero_row_player_results(self) -> None:
        empty_df = pl.DataFrame(
            {"user_id": pl.Series([], dtype=pl.Int64), "total_points": pl.Series([], dtype=pl.Float64)}
        )
        result = CoinFlipResult(
            player_results=empty_df,
            total_interactions=0,
            success_counts={},
            total_points=0.0,
            players_above_threshold=0,
            threshold=100.0,
        )
        metrics = result.get_kpi_metrics()

        assert metrics["mean_points_per_player"] == 0.0
        assert metrics["median_points_per_player"] == 0.0
        assert metrics["total_points"] == 0.0
        assert metrics["pct_above_threshold"] == 0.0
