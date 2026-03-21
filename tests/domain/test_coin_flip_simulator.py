"""Tests for CoinFlipSimulator domain engine.

Verifies:
- Deterministic simulation with seeded RNG
- Correct interaction counts: sum(rolls_sink // avg_multiplier)
- Success distribution sums to total interactions
- Non-negative success counts and points
- Churn players receive boosted probabilities
- Edge cases: zero interactions, max_successes=1
- Protocol conformance (Simulator, SimulationResult)
- Performance: 100K players in <5 seconds
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import polars as pl
import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.protocols import SimulationResult, Simulator
from src.domain.simulators.coin_flip import CoinFlipSimulator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(sample_config_dict: dict[str, Any]) -> CoinFlipConfig:
    return CoinFlipConfig.from_dict(sample_config_dict)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorDeterminism:
    """Simulation must be fully deterministic when seeded."""

    def test_same_seed_same_results(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result_a = sim.simulate(sample_players_df, config, seed=42)
        result_b = sim.simulate(sample_players_df, config, seed=42)
        assert result_a.total_points == result_b.total_points
        assert result_a.total_interactions == result_b.total_interactions
        assert result_a.success_counts == result_b.success_counts

    def test_different_seed_different_results(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result_a = sim.simulate(sample_players_df, config, seed=42)
        result_b = sim.simulate(sample_players_df, config, seed=999)
        # With different seeds, results should (almost certainly) differ
        assert result_a.total_points != result_b.total_points


# ---------------------------------------------------------------------------
# Interaction count invariants
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorInteractions:
    """Verify interaction counts match the domain formula."""

    def test_total_interactions_equals_formula(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)

        expected_interactions = int(
            sample_players_df.select(
                (pl.col("rolls_sink") // pl.col("avg_multiplier")).alias("interactions")
            )["interactions"].sum()
        )
        assert result.total_interactions == expected_interactions

    def test_success_distribution_sums_to_total(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        assert sum(result.success_counts.values()) == result.total_interactions

    def test_success_counts_non_negative(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        for depth, count in result.success_counts.items():
            assert count >= 0, f"Negative count at depth {depth}"

    def test_success_counts_keys_range(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        # Keys should be 0..max_successes
        assert set(result.success_counts.keys()) == set(range(config.max_successes + 1))


# ---------------------------------------------------------------------------
# Points invariants
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorPoints:
    """Verify point calculations are correct and non-negative."""

    def test_total_points_non_negative(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        assert result.total_points >= 0.0

    def test_player_points_non_negative(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        df = result.player_results
        assert (df["total_points"] >= 0.0).all()

    def test_total_points_equals_player_sum(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        player_sum = result.player_results["total_points"].sum()
        assert result.total_points == pytest.approx(player_sum)


# ---------------------------------------------------------------------------
# Churn boost
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorChurnBoost:
    """Churn players should statistically outperform non-churn players."""

    def test_churn_players_get_higher_average_points(self) -> None:
        """Run with enough players so statistical effect is clear."""
        np.random.default_rng(seed=123)
        n = 5000
        players = pl.DataFrame(
            {
                "user_id": list(range(1, n + 1)),
                "rolls_sink": [100] * n,
                "avg_multiplier": [10] * n,
                "about_to_churn": [True] * (n // 2) + [False] * (n // 2),
            }
        )
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=[0.6, 0.5, 0.5, 0.5, 0.5],
            point_values=[1.0, 2.0, 4.0, 8.0, 16.0],
            churn_boost_multiplier=1.3,
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        df = result.player_results

        churn_mean = df.filter(pl.col("about_to_churn"))["total_points"].mean()
        non_churn_mean = df.filter(~pl.col("about_to_churn"))["total_points"].mean()
        assert churn_mean > non_churn_mean  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorEdgeCases:
    """Verify correct handling of boundary conditions."""

    def test_zero_interactions_player(self) -> None:
        """Player with rolls_sink < avg_multiplier gets 0 interactions and 0 points."""
        players = pl.DataFrame(
            {
                "user_id": [1],
                "rolls_sink": [5],
                "avg_multiplier": [10],
                "about_to_churn": [False],
            }
        )
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=[0.6, 0.5, 0.5, 0.5, 0.5],
            point_values=[1.0, 2.0, 4.0, 8.0, 16.0],
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        assert result.total_interactions == 0
        assert result.total_points == 0.0
        assert result.player_results["total_points"][0] == 0.0

    def test_max_successes_one(self) -> None:
        """Single-flip chain: each interaction is either 0 or 1 success."""
        players = pl.DataFrame(
            {
                "user_id": [1],
                "rolls_sink": [1000],
                "avg_multiplier": [1],
                "about_to_churn": [False],
            }
        )
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=[0.5],
            point_values=[10.0],
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        # Success counts should only have keys 0 and 1
        assert set(result.success_counts.keys()) == {0, 1}
        assert sum(result.success_counts.values()) == 1000

    def test_all_players_zero_interactions(self) -> None:
        players = pl.DataFrame(
            {
                "user_id": [1, 2, 3],
                "rolls_sink": [1, 2, 3],
                "avg_multiplier": [10, 10, 10],
                "about_to_churn": [False, False, False],
            }
        )
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=[0.6, 0.5, 0.5, 0.5, 0.5],
            point_values=[1.0, 2.0, 4.0, 8.0, 16.0],
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        assert result.total_interactions == 0
        assert result.total_points == 0.0

    def test_probability_one_always_succeeds(self) -> None:
        """With probability=1.0 for all flips, every interaction reaches max depth."""
        players = pl.DataFrame(
            {
                "user_id": [1],
                "rolls_sink": [100],
                "avg_multiplier": [1],
                "about_to_churn": [False],
            }
        )
        config = CoinFlipConfig(
            max_successes=3,
            probabilities=[1.0, 1.0, 1.0],
            point_values=[1.0, 2.0, 4.0],
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        # All 100 interactions should reach max depth (3 successes)
        assert result.success_counts.get(3, 0) == 100
        # cumulative points per interaction = 1+2+4 = 7, * avg_mult=1 → 7 per interaction
        assert result.total_points == pytest.approx(7.0 * 100)

    def test_probability_zero_always_fails(self) -> None:
        """With probability=0.0 for first flip, all interactions get 0 successes."""
        players = pl.DataFrame(
            {
                "user_id": [1],
                "rolls_sink": [100],
                "avg_multiplier": [1],
                "about_to_churn": [False],
            }
        )
        config = CoinFlipConfig(
            max_successes=3,
            probabilities=[0.0, 1.0, 1.0],
            point_values=[1.0, 2.0, 4.0],
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        assert result.success_counts.get(0, 0) == 100
        assert result.total_points == 0.0

    def test_all_zero_probabilities(self) -> None:
        """Config with probabilities=(0.0, 0.0, 0.0): all interactions end at depth 0."""
        players = pl.DataFrame(
            {
                "user_id": list(range(1, 51)),
                "rolls_sink": [200] * 50,
                "avg_multiplier": [10] * 50,
                "about_to_churn": [False] * 50,
            }
        )
        config = CoinFlipConfig(
            max_successes=3,
            probabilities=(0.0, 0.0, 0.0),
            point_values=(1.0, 2.0, 4.0),
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)

        # Every interaction should end at depth 0 (first flip fails)
        total_interactions = result.total_interactions
        assert result.success_counts.get(0, 0) == total_interactions
        assert result.success_counts.get(1, 0) == 0
        assert result.success_counts.get(2, 0) == 0
        assert result.success_counts.get(3, 0) == 0
        assert result.total_points == 0.0

    def test_all_one_probabilities(self) -> None:
        """Config with probabilities=(1.0, 1.0, 1.0): all interactions reach max depth."""
        players = pl.DataFrame(
            {
                "user_id": list(range(1, 51)),
                "rolls_sink": [200] * 50,
                "avg_multiplier": [10] * 50,
                "about_to_churn": [False] * 50,
            }
        )
        config = CoinFlipConfig(
            max_successes=3,
            probabilities=(1.0, 1.0, 1.0),
            point_values=(1.0, 2.0, 4.0),
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)

        # Every interaction should reach max depth (3 successes)
        total_interactions = result.total_interactions
        assert result.success_counts.get(3, 0) == total_interactions
        assert result.success_counts.get(0, 0) == 0
        assert result.success_counts.get(1, 0) == 0
        assert result.success_counts.get(2, 0) == 0
        # Each interaction earns 1+2+4 = 7 points * avg_multiplier=10
        assert result.total_points == pytest.approx(7.0 * 10 * total_interactions)


# ---------------------------------------------------------------------------
# Result methods
# ---------------------------------------------------------------------------


class TestCoinFlipResultMethods:
    """Verify CoinFlipResult data accessors."""

    def test_to_summary_dict_contains_expected_keys(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        summary = result.to_summary_dict()
        assert "total_interactions" in summary
        assert "total_points" in summary
        assert "players_above_threshold" in summary

    def test_to_dataframe_returns_polars_df(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        df = result.to_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert "user_id" in df.columns

    def test_get_distribution_returns_str_int_dict(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        dist = result.get_distribution()
        assert isinstance(dist, dict)
        assert all(isinstance(k, str) for k in dist)
        assert all(isinstance(v, int) for v in dist.values())

    def test_get_kpi_metrics_returns_floats(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        kpis = result.get_kpi_metrics()
        assert isinstance(kpis, dict)
        assert all(isinstance(v, float) for v in kpis.values())

    def test_players_above_threshold(self) -> None:
        """Threshold counting should be accurate."""
        players = pl.DataFrame(
            {
                "user_id": [1, 2],
                "rolls_sink": [1000, 10],
                "avg_multiplier": [1, 1],
                "about_to_churn": [False, False],
            }
        )
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=[1.0, 1.0, 1.0, 1.0, 1.0],
            point_values=[1.0, 2.0, 4.0, 8.0, 16.0],
            reward_threshold=100.0,
        )
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)
        # Player 1: 1000 interactions * 31 points = 31000 (above threshold)
        # Player 2: 10 interactions * 31 points = 310 (above threshold)
        assert result.players_above_threshold == 2


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorProtocol:
    """Verify protocol contract compliance."""

    def test_simulator_implements_protocol(self) -> None:
        sim = CoinFlipSimulator()
        assert isinstance(sim, Simulator)

    def test_result_implements_protocol(
        self,
        sample_players_df: pl.DataFrame,
        sample_config_dict: dict[str, Any],
    ) -> None:
        sim = CoinFlipSimulator()
        config = _make_config(sample_config_dict)
        result = sim.simulate(sample_players_df, config, seed=42)
        assert isinstance(result, SimulationResult)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestCoinFlipSimulatorValidation:
    """Verify input validation catches bad DataFrames."""

    def test_zero_avg_multiplier_returns_validation_error(self) -> None:
        players = pl.DataFrame(
            {
                "user_id": [1],
                "rolls_sink": [100],
                "avg_multiplier": [0],
                "about_to_churn": [False],
            }
        )
        simulator = CoinFlipSimulator()
        errors = simulator.validate_input(players)
        assert len(errors) > 0
        assert "avg_multiplier" in errors[0]

    def test_valid_input_returns_no_errors(
        self,
        sample_players_df: pl.DataFrame,
    ) -> None:
        sim = CoinFlipSimulator()
        errors = sim.validate_input(sample_players_df)
        assert errors == []

    def test_missing_user_id_column(self) -> None:
        sim = CoinFlipSimulator()
        df = pl.DataFrame({"rolls_sink": [100], "avg_multiplier": [10], "about_to_churn": [False]})
        errors = sim.validate_input(df)
        assert any("user_id" in e for e in errors)

    def test_missing_rolls_sink_column(self) -> None:
        sim = CoinFlipSimulator()
        df = pl.DataFrame({"user_id": [1], "avg_multiplier": [10], "about_to_churn": [False]})
        errors = sim.validate_input(df)
        assert any("rolls_sink" in e for e in errors)

    def test_missing_avg_multiplier_column(self) -> None:
        sim = CoinFlipSimulator()
        df = pl.DataFrame({"user_id": [1], "rolls_sink": [100], "about_to_churn": [False]})
        errors = sim.validate_input(df)
        assert any("avg_multiplier" in e for e in errors)

    def test_missing_about_to_churn_column(self) -> None:
        sim = CoinFlipSimulator()
        df = pl.DataFrame({"user_id": [1], "rolls_sink": [100], "avg_multiplier": [10]})
        errors = sim.validate_input(df)
        assert any("about_to_churn" in e for e in errors)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCoinFlipSimulatorPerformance:
    """Performance tests — skipped in normal test runs."""

    def test_100k_players_under_5_seconds(self) -> None:
        rng = np.random.default_rng(seed=77)
        n = 100_000
        players = pl.DataFrame(
            {
                "user_id": list(range(1, n + 1)),
                "rolls_sink": rng.integers(50, 2000, size=n).tolist(),
                "avg_multiplier": rng.choice([1, 2, 5, 10, 20, 50], size=n).tolist(),
                "about_to_churn": rng.choice([True, False], size=n, p=[0.1, 0.9]).tolist(),
            }
        )
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=[0.60, 0.50, 0.50, 0.50, 0.50],
            point_values=[1.0, 2.0, 4.0, 8.0, 16.0],
        )
        sim = CoinFlipSimulator()
        start = time.perf_counter()
        result = sim.simulate(players, config, seed=42)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s, expected <5s"
        assert result.total_interactions > 0
