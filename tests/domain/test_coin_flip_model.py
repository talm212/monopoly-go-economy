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
        with pytest.raises(ValueError, match="probability at index 1"):
            CoinFlipConfig(
                max_successes=2,
                probabilities=(0.5, float("nan")),
                point_values=(1.0, 2.0),
            )

    def test_nan_first_probability_raises(self) -> None:
        with pytest.raises(ValueError, match="probability at index 0"):
            CoinFlipConfig(
                max_successes=1,
                probabilities=(float("nan"),),
                point_values=(1.0,),
            )

    def test_inf_point_value_raises(self) -> None:
        with pytest.raises(ValueError, match="point_values at index 1"):
            CoinFlipConfig(
                max_successes=2,
                probabilities=(0.5, 0.5),
                point_values=(1.0, float("inf")),
            )

    def test_negative_inf_point_value_raises(self) -> None:
        with pytest.raises(ValueError, match="point_values at index 0"):
            CoinFlipConfig(
                max_successes=1,
                probabilities=(0.5,),
                point_values=(float("-inf"),),
            )

    def test_inf_probability_raises(self) -> None:
        with pytest.raises(ValueError, match="probability at index 0"):
            CoinFlipConfig(
                max_successes=1,
                probabilities=(float("inf"),),
                point_values=(1.0,),
            )

    def test_nan_point_value_raises(self) -> None:
        with pytest.raises(ValueError, match="point_values at index 0"):
            CoinFlipConfig(
                max_successes=1,
                probabilities=(0.5,),
                point_values=(float("nan"),),
            )


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


# ---------------------------------------------------------------------------
# CoinFlipResult — ResultsDisplay protocol methods
# ---------------------------------------------------------------------------


class TestCoinFlipResultsDisplay:
    """Verify CoinFlipResult satisfies the ResultsDisplay protocol contract."""

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

    def test_get_kpi_cards_returns_spec_kpis(
        self, result_with_churn: CoinFlipResult,
    ) -> None:
        cards = result_with_churn.get_kpi_cards()
        assert len(cards) == 3
        expected_labels = {
            "Total Interactions",
            "Total Points",
            "Players Above Threshold",
        }
        assert set(cards.keys()) == expected_labels

    def test_get_kpi_cards_values_match_result(
        self, result_with_churn: CoinFlipResult,
    ) -> None:
        cards = result_with_churn.get_kpi_cards()
        assert cards["Total Interactions"][0] == result_with_churn.total_interactions
        assert cards["Total Points"][0] == result_with_churn.total_points
        assert cards["Players Above Threshold"][0] == result_with_churn.players_above_threshold

    def test_get_kpi_cards_includes_help_text(
        self, result_with_churn: CoinFlipResult,
    ) -> None:
        cards = result_with_churn.get_kpi_cards()
        for label, (value, help_text) in cards.items():
            assert isinstance(help_text, str)
            assert len(help_text) > 0, f"Help text for '{label}' should not be empty"

    def test_get_segments_with_churn_column(
        self, result_with_churn: CoinFlipResult,
    ) -> None:
        segments = result_with_churn.get_segments()
        assert segments is not None
        assert "churn" in segments
        assert "non-churn" in segments
        for seg_name, metrics in segments.items():
            assert "Player Count" in metrics
            assert "Avg Points / Player" in metrics
            assert "Median Points / Player" in metrics
            assert "Total Points" in metrics

    def test_get_segments_churn_values(
        self, result_with_churn: CoinFlipResult,
    ) -> None:
        segments = result_with_churn.get_segments()
        assert segments is not None
        churn = segments["churn"]
        assert churn["Player Count"] == 2.0
        # Churn players: user_id 1 (50.0) and user_id 3 (200.0)
        assert churn["Total Points"] == 250.0
        assert churn["Avg Points / Player"] == 125.0

    def test_get_segments_without_churn_returns_none(
        self, result_without_churn: CoinFlipResult,
    ) -> None:
        segments = result_without_churn.get_segments()
        assert segments is None

    def test_get_dataframe_returns_player_results(
        self, result_with_churn: CoinFlipResult,
    ) -> None:
        df = result_with_churn.get_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert df.height == 4
        assert "user_id" in df.columns
        assert "total_points" in df.columns

    def test_get_kpi_cards_empty_dataframe(self) -> None:
        empty_df = pl.DataFrame(
            {
                "user_id": pl.Series([], dtype=pl.Int64),
                "total_points": pl.Series([], dtype=pl.Float64),
            }
        )
        result = CoinFlipResult(
            player_results=empty_df,
            total_interactions=0,
            success_counts={},
            total_points=0.0,
            players_above_threshold=0,
            threshold=100.0,
        )
        cards = result.get_kpi_cards()
        assert cards["Total Interactions"][0] == 0
        assert cards["Total Points"][0] == 0.0
        assert cards["Players Above Threshold"][0] == 0

    def test_get_segments_with_empty_churn_segment(self) -> None:
        """All players are non-churn; churn segment should have zero counts."""
        df = pl.DataFrame(
            {
                "user_id": [1, 2],
                "total_points": [10.0, 20.0],
                "about_to_churn": [False, False],
            }
        )
        result = CoinFlipResult(
            player_results=df,
            total_interactions=10,
            success_counts={0: 5, 1: 5},
            total_points=30.0,
            players_above_threshold=0,
            threshold=100.0,
        )
        segments = result.get_segments()
        assert segments is not None
        assert segments["churn"]["Player Count"] == 0.0
        assert segments["non-churn"]["Player Count"] == 2.0
