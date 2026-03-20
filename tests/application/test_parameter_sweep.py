"""Tests for ParameterSweep use case.

Validates that parameter sweeps produce correct results:
- Multiple sweep points with expected counts
- Single-value sweeps
- Deterministic results with seeded RNG
- DataFrame output format
- Invalid parameter handling
"""

from __future__ import annotations

import polars as pl
import pytest

from src.application.parameter_sweep import ParameterSweep, SweepResult
from src.domain.simulators.coin_flip import CoinFlipSimulator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def small_players() -> pl.DataFrame:
    """Create a small player DataFrame (100 players) for sweep tests."""
    return pl.DataFrame(
        {
            "user_id": list(range(100)),
            "rolls_sink": [100] * 100,
            "avg_multiplier": [10.0] * 100,
            "about_to_churn": [False] * 80 + [True] * 20,
        }
    )


@pytest.fixture
def base_config() -> dict[str, object]:
    """Base configuration dict for coin flip."""
    return {
        "max_successes": 5,
        "probabilities": [0.6, 0.5, 0.4, 0.3, 0.2],
        "point_values": [1.0, 2.0, 4.0, 8.0, 16.0],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


@pytest.fixture
def sweep(simulator: CoinFlipSimulator) -> ParameterSweep:
    """Create a ParameterSweep with a real CoinFlipSimulator."""
    return ParameterSweep(simulator)


@pytest.fixture
def simulator() -> CoinFlipSimulator:
    return CoinFlipSimulator()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParameterSweepMultipleValues:
    """Sweep p_success_1 from 0.1 to 0.9 in 5 steps -> verify 5 results."""

    def test_sweep_produces_correct_number_of_points(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.1, 0.3, 0.5, 0.7, 0.9]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        assert len(result.sweep_points) == 5

    def test_sweep_points_have_correct_param_values(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.1, 0.3, 0.5, 0.7, 0.9]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        actual_values = [sp.param_value for sp in result.sweep_points]
        assert actual_values == values

    def test_sweep_points_contain_kpi_metrics(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.1, 0.3, 0.5, 0.7, 0.9]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        for sp in result.sweep_points:
            assert "mean_points_per_player" in sp.kpi_metrics
            assert "median_points_per_player" in sp.kpi_metrics
            assert "total_points" in sp.kpi_metrics
            assert "pct_above_threshold" in sp.kpi_metrics

    def test_higher_probability_yields_higher_mean_points(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        """Higher p_success_1 should generally increase mean points."""
        values = [0.1, 0.9]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        low_mean = result.sweep_points[0].kpi_metrics["mean_points_per_player"]
        high_mean = result.sweep_points[1].kpi_metrics["mean_points_per_player"]
        assert high_mean > low_mean


class TestParameterSweepSingleValue:
    """Sweep with single value -> verify 1 result."""

    def test_single_value_sweep(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=[0.5],
            seed=42,
        )
        assert len(result.sweep_points) == 1
        assert result.sweep_points[0].param_value == 0.5


class TestParameterSweepDeterministic:
    """Sweep with seeded RNG -> verify deterministic results."""

    def test_seeded_sweep_is_deterministic(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.3, 0.5, 0.7]
        result1 = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=123,
        )
        result2 = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=123,
        )
        for sp1, sp2 in zip(result1.sweep_points, result2.sweep_points):
            assert sp1.kpi_metrics == sp2.kpi_metrics


class TestSweepResultToDataframe:
    """to_dataframe() returns correct columns."""

    def test_dataframe_has_expected_columns(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.3, 0.5, 0.7]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        df = result.to_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert "param_value" in df.columns
        assert "mean_points_per_player" in df.columns
        assert "median_points_per_player" in df.columns
        assert "total_points" in df.columns
        assert "pct_above_threshold" in df.columns

    def test_dataframe_row_count_matches_sweep_points(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.3, 0.5, 0.7]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        df = result.to_dataframe()
        assert df.height == 3

    def test_dataframe_param_values_are_correct(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [0.2, 0.4, 0.6, 0.8]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=values,
            seed=42,
        )
        df = result.to_dataframe()
        assert df["param_value"].to_list() == values


class TestParameterSweepFlatParam:
    """Sweep a flat (non-indexed) parameter like reward_threshold."""

    def test_sweep_reward_threshold(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [50.0, 100.0, 200.0]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="reward_threshold",
            values=values,
            seed=42,
        )
        assert len(result.sweep_points) == 3
        # Higher threshold should reduce pct_above_threshold
        pct_low_threshold = result.sweep_points[0].kpi_metrics["pct_above_threshold"]
        pct_high_threshold = result.sweep_points[2].kpi_metrics["pct_above_threshold"]
        assert pct_low_threshold >= pct_high_threshold


class TestParameterSweepPointValues:
    """Sweep an indexed point_values parameter."""

    def test_sweep_point_values_0(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        values = [1.0, 5.0, 10.0]
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="point_values.0",
            values=values,
            seed=42,
        )
        assert len(result.sweep_points) == 3
        # Higher base point value should yield higher total points
        low_total = result.sweep_points[0].kpi_metrics["total_points"]
        high_total = result.sweep_points[2].kpi_metrics["total_points"]
        assert high_total > low_total


class TestParameterSweepInvalidParam:
    """Invalid param name raises ValueError."""

    def test_invalid_param_raises_error(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        with pytest.raises(ValueError, match="Unknown parameter"):
            sweep.run(
                players=small_players,
                base_config=base_config,
                param_name="nonexistent_param",
                values=[1.0],
                seed=42,
            )

    def test_invalid_index_raises_error(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        with pytest.raises(ValueError, match="out of range"):
            sweep.run(
                players=small_players,
                base_config=base_config,
                param_name="probabilities.99",
                values=[0.5],
                seed=42,
            )


class TestSweepResultParamName:
    """SweepResult stores param_name correctly."""

    def test_param_name_stored(
        self,
        sweep: ParameterSweep,
        small_players: pl.DataFrame,
        base_config: dict[str, object],
    ) -> None:
        result = sweep.run(
            players=small_players,
            base_config=base_config,
            param_name="probabilities.0",
            values=[0.5],
            seed=42,
        )
        assert result.param_name == "probabilities.0"
