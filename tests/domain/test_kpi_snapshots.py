"""KPI snapshot regression tests for the coin-flip simulation engine.

Runs the simulator with a fixed seed and known player data, then asserts
EXACT KPI values.  Any change to the simulation logic that alters numerical
output will break these tests, preventing silent regressions.

Snapshot values were captured with seed=42 on the 5-player dataset defined
in the module-level fixtures below.
"""

from __future__ import annotations

import polars as pl
import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.simulators.coin_flip import CoinFlipSimulator

# ---------------------------------------------------------------------------
# Fixed test data (5 players)
# ---------------------------------------------------------------------------

_PLAYERS = pl.DataFrame(
    {
        "user_id": [1, 2, 3, 4, 5],
        "rolls_sink": [100, 200, 50, 500, 1000],
        "avg_multiplier": [10, 20, 5, 50, 100],
        "about_to_churn": [False, False, True, False, False],
    }
)

_CONFIG = CoinFlipConfig(
    max_successes=5,
    probabilities=(0.6, 0.5, 0.5, 0.5, 0.5),
    point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
    churn_boost_multiplier=1.3,
    reward_threshold=100.0,
)

_SEED = 42


@pytest.fixture(scope="module")
def snapshot_result():
    """Run the simulation once for the entire module and share the result."""
    sim = CoinFlipSimulator()
    return sim.simulate(_PLAYERS, _CONFIG, seed=_SEED)


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------


class TestKpiSnapshotTotalPoints:
    """Exact total_points must not drift."""

    def test_kpi_snapshot_total_points(self, snapshot_result) -> None:
        assert snapshot_result.total_points == 2540.0


class TestKpiSnapshotMeanMedian:
    """Mean and median points per player must be exact."""

    def test_kpi_snapshot_mean_median(self, snapshot_result) -> None:
        kpis = snapshot_result.get_kpi_metrics()
        assert kpis["mean_points_per_player"] == 508.0
        assert kpis["median_points_per_player"] == 350.0


class TestKpiSnapshotPctAboveThreshold:
    """Percentage of players above the reward threshold must be exact."""

    def test_kpi_snapshot_pct_above_threshold(self, snapshot_result) -> None:
        kpis = snapshot_result.get_kpi_metrics()
        assert kpis["pct_above_threshold"] == 1.0


class TestKpiSnapshotDistribution:
    """Success-depth distribution must match the snapshot exactly."""

    def test_kpi_snapshot_distribution(self, snapshot_result) -> None:
        expected_success_counts = {0: 23, 1: 12, 2: 8, 3: 0, 4: 3, 5: 4}
        assert snapshot_result.success_counts == expected_success_counts


class TestKpiSnapshotChurnVsNonChurn:
    """Mean points must be exact for churn and non-churn segments."""

    def test_kpi_snapshot_churn_vs_non_churn(self, snapshot_result) -> None:
        df = snapshot_result.player_results
        churn_mean = df.filter(pl.col("about_to_churn"))["total_points"].mean()
        non_churn_mean = df.filter(~pl.col("about_to_churn"))["total_points"].mean()
        assert churn_mean == 720.0
        assert non_churn_mean == 455.0


class TestKpiSnapshotTotalInteractions:
    """Total interaction count must be exact."""

    def test_kpi_snapshot_total_interactions(self, snapshot_result) -> None:
        assert snapshot_result.total_interactions == 50
