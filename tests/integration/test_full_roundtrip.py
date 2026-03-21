"""Full simulation-to-store-to-load roundtrip integration test.

Runs a real CoinFlipSimulator simulation with known config and seed,
saves the results via LocalSimulationStore (including player_results Parquet),
then loads everything back and verifies exact KPI and distribution matches.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.simulators.coin_flip import CoinFlipSimulator
from src.infrastructure.store.local_store import LocalSimulationStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> LocalSimulationStore:
    """Create a LocalSimulationStore backed by a temporary directory."""
    return LocalSimulationStore(store_dir=str(tmp_path / "roundtrip_store"))


@pytest.fixture
def config() -> CoinFlipConfig:
    """Known CoinFlipConfig for deterministic testing."""
    return CoinFlipConfig(
        max_successes=5,
        probabilities=(0.60, 0.50, 0.40, 0.30, 0.20),
        point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
        churn_boost_multiplier=1.3,
        reward_threshold=100.0,
    )


@pytest.fixture
def players() -> pl.DataFrame:
    """500-player DataFrame for integration testing."""
    import numpy as np

    rng = np.random.default_rng(seed=99)
    n = 500
    return pl.DataFrame(
        {
            "user_id": list(range(1, n + 1)),
            "rolls_sink": rng.integers(50, 1000, size=n).tolist(),
            "avg_multiplier": rng.choice([1, 2, 5, 10, 20], size=n).tolist(),
            "about_to_churn": rng.choice(
                [True, False], size=n, p=[0.15, 0.85]
            ).tolist(),
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullSimulationRoundtrip:
    """Run simulation -> save -> load -> assert exact match."""

    def test_kpi_values_match_after_roundtrip(
        self,
        store: LocalSimulationStore,
        config: CoinFlipConfig,
        players: pl.DataFrame,
    ) -> None:
        """KPI metrics from the original result match those recomputed from loaded data."""
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)

        # Save run metadata and player results
        run_data = {
            "feature": "coin_flip",
            "config": config.to_dict(),
            "result_summary": result.to_summary_dict(),
            "distribution": result.get_distribution(),
        }
        run_id = store.save_run(run_data, player_results=result.player_results)

        # Load back
        loaded_run = store.get_run(run_id)
        loaded_players = store.load_player_results(run_id)

        assert loaded_players is not None

        # Verify result_summary matches
        assert loaded_run["result_summary"]["total_interactions"] == result.total_interactions
        assert loaded_run["result_summary"]["total_points"] == pytest.approx(
            result.total_points
        )
        assert (
            loaded_run["result_summary"]["players_above_threshold"]
            == result.players_above_threshold
        )

        # Verify KPIs by recomputing from loaded player results
        original_kpis = result.get_kpi_metrics()
        loaded_mean = float(loaded_players["total_points"].mean())  # type: ignore[arg-type]
        loaded_median = float(loaded_players["total_points"].median())  # type: ignore[arg-type]
        loaded_total = float(loaded_players["total_points"].sum())

        assert loaded_mean == pytest.approx(original_kpis["mean_points_per_player"])
        assert loaded_median == pytest.approx(original_kpis["median_points_per_player"])
        assert loaded_total == pytest.approx(original_kpis["total_points"])

    def test_distribution_matches_after_roundtrip(
        self,
        store: LocalSimulationStore,
        config: CoinFlipConfig,
        players: pl.DataFrame,
    ) -> None:
        """Success distribution stored in JSON matches the original exactly."""
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)

        run_data = {
            "feature": "coin_flip",
            "config": config.to_dict(),
            "result_summary": result.to_summary_dict(),
            "distribution": result.get_distribution(),
        }
        run_id = store.save_run(run_data, player_results=result.player_results)

        loaded_run = store.get_run(run_id)
        loaded_dist = loaded_run["distribution"]
        original_dist = result.get_distribution()

        assert loaded_dist == original_dist

    def test_player_results_dataframe_matches_exactly(
        self,
        store: LocalSimulationStore,
        config: CoinFlipConfig,
        players: pl.DataFrame,
    ) -> None:
        """Loaded player_results DataFrame has identical schema, rows, and values."""
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)

        run_data = {
            "feature": "coin_flip",
            "config": config.to_dict(),
            "result_summary": result.to_summary_dict(),
            "distribution": result.get_distribution(),
        }
        run_id = store.save_run(run_data, player_results=result.player_results)

        loaded_players = store.load_player_results(run_id)
        assert loaded_players is not None

        original = result.player_results

        # Schema match
        assert loaded_players.schema == original.schema

        # Row count match
        assert loaded_players.height == original.height

        # Column-by-column value match
        assert loaded_players["user_id"].to_list() == original["user_id"].to_list()
        assert loaded_players["total_points"].to_list() == pytest.approx(
            original["total_points"].to_list()
        )
        assert loaded_players["num_interactions"].to_list() == original["num_interactions"].to_list()

    def test_config_survives_roundtrip(
        self,
        store: LocalSimulationStore,
        config: CoinFlipConfig,
        players: pl.DataFrame,
    ) -> None:
        """Config dict stored in JSON can reconstruct an identical CoinFlipConfig."""
        sim = CoinFlipSimulator()
        result = sim.simulate(players, config, seed=42)

        run_data = {
            "feature": "coin_flip",
            "config": config.to_dict(),
            "result_summary": result.to_summary_dict(),
            "distribution": result.get_distribution(),
        }
        run_id = store.save_run(run_data, player_results=result.player_results)

        loaded_run = store.get_run(run_id)
        restored_config = CoinFlipConfig.from_dict(loaded_run["config"])

        assert restored_config == config
