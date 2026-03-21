"""Performance benchmark tests for the coin-flip simulation engine.

These tests track simulation performance and fail if there is a
significant regression (>20% above the time budget).  They are excluded
from the default test run via the ``benchmark`` marker and must be
invoked explicitly with ``-m benchmark``.
"""

import time

import numpy as np
import polars as pl
import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.simulators.coin_flip import CoinFlipSimulator

pytestmark = pytest.mark.benchmark


def _generate_players(n: int, seed: int = 42) -> pl.DataFrame:
    """Generate a synthetic player DataFrame with *n* rows."""
    rng = np.random.default_rng(seed)
    return pl.DataFrame(
        {
            "user_id": list(range(n)),
            "rolls_sink": rng.integers(10, 1000, size=n).tolist(),
            "avg_multiplier": rng.integers(1, 100, size=n).tolist(),
            "about_to_churn": rng.choice(
                [True, False], size=n, p=[0.1, 0.9]
            ).tolist(),
        }
    )


CONFIG = CoinFlipConfig(
    max_successes=5,
    probabilities=(0.6, 0.5, 0.5, 0.5, 0.5),
    point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
)


class TestSimulationPerformance:
    """Regression-guard benchmarks for the vectorized simulator."""

    def test_100k_players_under_3_seconds(self) -> None:
        players = _generate_players(100_000)
        sim = CoinFlipSimulator()

        start = time.perf_counter()
        result = sim.simulate(players, CONFIG, seed=42)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"100K simulation took {elapsed:.2f}s (limit: 3.0s)"
        assert result.total_interactions > 0

    def test_1m_players_under_15_seconds(self) -> None:
        players = _generate_players(1_000_000)
        sim = CoinFlipSimulator()

        start = time.perf_counter()
        result = sim.simulate(players, CONFIG, seed=42)
        elapsed = time.perf_counter() - start

        assert elapsed < 15.0, f"1M simulation took {elapsed:.2f}s (limit: 15.0s)"
        assert result.total_interactions > 0


# ---------------------------------------------------------------------------
# Loot table benchmark
# ---------------------------------------------------------------------------

from src.domain.models.loot_table import LootItem, LootTableConfig
from src.domain.simulators.loot_table import LootTableSimulator


def _generate_loot_players(n: int, seed: int = 42) -> pl.DataFrame:
    """Generate a synthetic player DataFrame with *n* rows for loot table."""
    return pl.DataFrame({"user_id": list(range(n))})


LOOT_CONFIG = LootTableConfig(
    items=(
        LootItem(name="gold_coin", weight=50.0, rarity="common", value=10.0),
        LootItem(name="silver_ring", weight=30.0, rarity="uncommon", value=25.0),
        LootItem(name="ruby_gem", weight=12.0, rarity="rare", value=100.0),
        LootItem(name="dragon_shield", weight=5.0, rarity="epic", value=500.0),
        LootItem(name="excalibur", weight=3.0, rarity="legendary", value=2000.0),
    ),
    num_rolls=20,
    pity_threshold=10,
)


class TestLootTablePerformance:
    """Benchmark for the loot table simulator."""

    def test_100k_loot_table_completes(self) -> None:
        """100K players through LootTableSimulator with 5 items and pity enabled.

        Establishes baseline benchmark; no time assertion yet, just verifies
        the simulation completes and produces valid output.
        """
        players = _generate_loot_players(100_000)
        sim = LootTableSimulator()

        start = time.perf_counter()
        result = sim.simulate(players, LOOT_CONFIG, seed=42)
        elapsed = time.perf_counter() - start

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Loot table 100K benchmark: %.2fs, total_rolls=%d, total_value=%.2f",
            elapsed,
            result.total_rolls,
            result.total_value,
        )

        # Basic correctness assertions
        assert result.total_rolls == 100_000 * 20
        assert result.total_value > 0
        assert result.player_results.height == 100_000
        assert "total_value" in result.player_results.columns
        assert "rare_count" in result.player_results.columns
        assert "legendary_count" in result.player_results.columns
