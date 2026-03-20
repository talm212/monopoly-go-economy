"""Tests for CoinFlipConfig.validate() edge cases, CoinFlipResult.get_kpi_metrics(),
and CoinFlipResult.to_analysis_context().

Covers zero-coverage paths:
- validate() rejects NaN probability
- validate() rejects inf point value
- get_kpi_metrics() with zero-row player_results DataFrame
- to_analysis_context() with and without churn segment data
"""

from __future__ import annotations

import math

import polars as pl
import pytest

from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult
from src.domain.protocols import FeatureAnalysisContext

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


# ---------------------------------------------------------------------------
# CoinFlipResult.to_analysis_context()
# ---------------------------------------------------------------------------


class TestToAnalysisContext:
    """Verify to_analysis_context() produces a correct FeatureAnalysisContext."""

    @pytest.fixture
    def config(self) -> CoinFlipConfig:
        return CoinFlipConfig(
            max_successes=3,
            probabilities=(0.6, 0.5, 0.4),
            point_values=(1.0, 2.0, 4.0),
            churn_boost_multiplier=1.3,
            reward_threshold=100.0,
        )

    @pytest.fixture
    def result_with_churn(self) -> CoinFlipResult:
        df = pl.DataFrame(
            {
                "user_id": [1, 2, 3, 4],
                "total_points": [50.0, 150.0, 200.0, 30.0],
                "about_to_churn": [True, False, True, False],
            }
        )
        return CoinFlipResult(
            player_results=df,
            total_interactions=100,
            success_counts={0: 40, 1: 30, 2: 20, 3: 10},
            total_points=430.0,
            players_above_threshold=2,
            threshold=100.0,
        )

    @pytest.fixture
    def result_without_churn(self) -> CoinFlipResult:
        df = pl.DataFrame(
            {
                "user_id": [1, 2],
                "total_points": [80.0, 120.0],
            }
        )
        return CoinFlipResult(
            player_results=df,
            total_interactions=50,
            success_counts={0: 25, 1: 15, 2: 10},
            total_points=200.0,
            players_above_threshold=1,
            threshold=100.0,
        )

    def test_returns_feature_analysis_context(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert isinstance(ctx, FeatureAnalysisContext)

    def test_feature_name_is_coin_flip(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert ctx.feature_name == "coin_flip"

    def test_config_matches_to_dict(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert ctx.config == config.to_dict()

    def test_kpi_metrics_present(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert "mean_points_per_player" in ctx.kpi_metrics
        assert "median_points_per_player" in ctx.kpi_metrics
        assert "total_points" in ctx.kpi_metrics
        assert "pct_above_threshold" in ctx.kpi_metrics

    def test_distribution_uses_string_keys(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert all(isinstance(k, str) for k in ctx.distribution)
        assert ctx.distribution == {"0": 40, "1": 30, "2": 20, "3": 10}

    def test_result_summary_includes_kpi_metrics(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert "mean_points_per_player" in ctx.result_summary
        assert "total_interactions" in ctx.result_summary

    def test_churn_segment_data_populated(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        assert ctx.segment_data is not None
        assert ctx.segment_data["churn_player_count"] == 2
        assert ctx.segment_data["non_churn_player_count"] == 2
        assert ctx.result_summary["churn_segment"] == ctx.segment_data

    def test_no_churn_column_gives_none_segment(
        self, result_without_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_without_churn.to_analysis_context(config)
        assert ctx.segment_data is None
        assert "churn_segment" not in ctx.result_summary

    def test_context_is_frozen(
        self, result_with_churn: CoinFlipResult, config: CoinFlipConfig,
    ) -> None:
        ctx = result_with_churn.to_analysis_context(config)
        with pytest.raises(AttributeError):
            ctx.feature_name = "other"  # type: ignore[misc]
