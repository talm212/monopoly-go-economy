"""Unit tests for optimizer comparison pure helper functions.

Tests the config diff, KPI delta calculation, and distribution comparison
data structures — no Streamlit rendering required.
"""

from __future__ import annotations

import pytest

from src.ui.components.optimizer_comparison import (
    compute_config_diff,
    compute_kpi_deltas,
    build_distribution_overlay_data,
    ConfigDiffRow,
    KpiDelta,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def original_config() -> dict[str, object]:
    return {
        "max_successes": 5,
        "probabilities": [0.6, 0.5, 0.4, 0.3, 0.2],
        "point_values": [1.0, 2.0, 5.0, 10.0, 50.0],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


@pytest.fixture
def optimized_config() -> dict[str, object]:
    return {
        "max_successes": 5,
        "probabilities": [0.7, 0.55, 0.4, 0.35, 0.25],
        "point_values": [1.0, 3.0, 5.0, 12.0, 50.0],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


@pytest.fixture
def original_kpis() -> dict[str, float]:
    return {
        "mean_points_per_player": 50.0,
        "median_points_per_player": 40.0,
        "total_points": 500_000.0,
        "pct_above_threshold": 0.15,
    }


@pytest.fixture
def optimized_kpis() -> dict[str, float]:
    return {
        "mean_points_per_player": 65.0,
        "median_points_per_player": 55.0,
        "total_points": 650_000.0,
        "pct_above_threshold": 0.22,
    }


@pytest.fixture
def original_distribution() -> dict[str, int]:
    return {"0": 4000, "1": 3000, "2": 2000, "3": 800, "4": 150, "5": 50}


@pytest.fixture
def optimized_distribution() -> dict[str, int]:
    return {"0": 3000, "1": 3200, "2": 2200, "3": 1000, "4": 400, "5": 200}


# ---------------------------------------------------------------------------
# compute_config_diff
# ---------------------------------------------------------------------------


class TestComputeConfigDiff:
    """Tests for detecting changed parameters between two configs."""

    def test_detects_changed_parameters(
        self,
        original_config: dict[str, object],
        optimized_config: dict[str, object],
    ) -> None:
        diff = compute_config_diff(original_config, optimized_config)
        changed_params = {row.parameter for row in diff}
        assert "probabilities" in changed_params
        assert "point_values" in changed_params

    def test_excludes_unchanged_parameters(
        self,
        original_config: dict[str, object],
        optimized_config: dict[str, object],
    ) -> None:
        diff = compute_config_diff(original_config, optimized_config)
        changed_params = {row.parameter for row in diff}
        assert "max_successes" not in changed_params
        assert "churn_boost_multiplier" not in changed_params
        assert "reward_threshold" not in changed_params

    def test_returns_config_diff_rows(
        self,
        original_config: dict[str, object],
        optimized_config: dict[str, object],
    ) -> None:
        diff = compute_config_diff(original_config, optimized_config)
        assert len(diff) > 0
        for row in diff:
            assert isinstance(row, ConfigDiffRow)
            assert row.parameter
            assert row.original_value is not None
            assert row.optimized_value is not None

    def test_empty_diff_for_identical_configs(
        self,
        original_config: dict[str, object],
    ) -> None:
        diff = compute_config_diff(original_config, original_config)
        assert diff == []

    def test_percentage_change_for_numeric_scalars(self) -> None:
        original = {"reward_threshold": 100.0, "max_successes": 5}
        optimized = {"reward_threshold": 120.0, "max_successes": 5}
        diff = compute_config_diff(original, optimized)
        assert len(diff) == 1
        row = diff[0]
        assert row.parameter == "reward_threshold"
        assert row.pct_change == pytest.approx(20.0)

    def test_handles_list_parameters_element_wise(self) -> None:
        original = {"probabilities": [0.5, 0.4]}
        optimized = {"probabilities": [0.6, 0.4]}
        diff = compute_config_diff(original, optimized)
        # Should produce a row for the list that changed
        assert len(diff) == 1
        assert diff[0].parameter == "probabilities"

    def test_handles_new_key_in_optimized(self) -> None:
        original: dict[str, object] = {"a": 1}
        optimized: dict[str, object] = {"a": 1, "b": 2}
        diff = compute_config_diff(original, optimized)
        assert len(diff) == 1
        assert diff[0].parameter == "b"
        assert diff[0].original_value is None
        assert diff[0].optimized_value == 2

    def test_handles_removed_key_in_optimized(self) -> None:
        original: dict[str, object] = {"a": 1, "b": 2}
        optimized: dict[str, object] = {"a": 1}
        diff = compute_config_diff(original, optimized)
        assert len(diff) == 1
        assert diff[0].parameter == "b"
        assert diff[0].original_value == 2
        assert diff[0].optimized_value is None


# ---------------------------------------------------------------------------
# compute_kpi_deltas
# ---------------------------------------------------------------------------


class TestComputeKpiDeltas:
    """Tests for KPI delta calculation between original and optimized runs."""

    def test_positive_deltas(
        self,
        original_kpis: dict[str, float],
        optimized_kpis: dict[str, float],
    ) -> None:
        deltas = compute_kpi_deltas(original_kpis, optimized_kpis)
        assert len(deltas) == 4
        for d in deltas:
            assert isinstance(d, KpiDelta)
            assert d.delta > 0  # all optimized values are higher in fixture

    def test_delta_values_are_correct(
        self,
        original_kpis: dict[str, float],
        optimized_kpis: dict[str, float],
    ) -> None:
        deltas = compute_kpi_deltas(original_kpis, optimized_kpis)
        delta_map = {d.metric: d for d in deltas}

        mean_d = delta_map["mean_points_per_player"]
        assert mean_d.original == pytest.approx(50.0)
        assert mean_d.optimized == pytest.approx(65.0)
        assert mean_d.delta == pytest.approx(15.0)
        assert mean_d.pct_change == pytest.approx(30.0)

    def test_negative_deltas(self) -> None:
        original = {"total_points": 1000.0}
        optimized = {"total_points": 800.0}
        deltas = compute_kpi_deltas(original, optimized)
        assert deltas[0].delta == pytest.approx(-200.0)
        assert deltas[0].pct_change == pytest.approx(-20.0)

    def test_zero_delta(self) -> None:
        kpis = {"metric_a": 42.0}
        deltas = compute_kpi_deltas(kpis, kpis)
        assert deltas[0].delta == pytest.approx(0.0)
        assert deltas[0].pct_change == pytest.approx(0.0)

    def test_zero_original_avoids_division_by_zero(self) -> None:
        original = {"metric_a": 0.0}
        optimized = {"metric_a": 10.0}
        deltas = compute_kpi_deltas(original, optimized)
        assert deltas[0].delta == pytest.approx(10.0)
        # pct_change should be None or inf-safe when original is zero
        assert deltas[0].pct_change is None

    def test_preserves_metric_order(
        self,
        original_kpis: dict[str, float],
        optimized_kpis: dict[str, float],
    ) -> None:
        deltas = compute_kpi_deltas(original_kpis, optimized_kpis)
        expected_order = list(original_kpis.keys())
        actual_order = [d.metric for d in deltas]
        assert actual_order == expected_order


# ---------------------------------------------------------------------------
# build_distribution_overlay_data
# ---------------------------------------------------------------------------


class TestBuildDistributionOverlayData:
    """Tests for distribution comparison data structure builder."""

    def test_returns_combined_rows(
        self,
        original_distribution: dict[str, int],
        optimized_distribution: dict[str, int],
    ) -> None:
        rows = build_distribution_overlay_data(
            original_distribution, optimized_distribution
        )
        # Each depth key produces 2 rows (original + optimized)
        all_keys = original_distribution.keys() | optimized_distribution.keys()
        assert len(rows) == len(all_keys) * 2

    def test_row_structure(
        self,
        original_distribution: dict[str, int],
        optimized_distribution: dict[str, int],
    ) -> None:
        rows = build_distribution_overlay_data(
            original_distribution, optimized_distribution
        )
        for row in rows:
            assert "Depth" in row
            assert "Count" in row
            assert "Run" in row
            assert row["Run"] in ("Original", "Optimized")

    def test_sorted_by_depth(
        self,
        original_distribution: dict[str, int],
        optimized_distribution: dict[str, int],
    ) -> None:
        rows = build_distribution_overlay_data(
            original_distribution, optimized_distribution
        )
        depths = [row["Depth"] for row in rows if row["Run"] == "Original"]
        numeric_depths = [int(d) for d in depths]
        assert numeric_depths == sorted(numeric_depths)

    def test_missing_keys_filled_with_zero(self) -> None:
        original = {"0": 100, "1": 50}
        optimized = {"0": 80, "2": 30}
        rows = build_distribution_overlay_data(original, optimized)
        row_map = {(r["Depth"], r["Run"]): r["Count"] for r in rows}
        assert row_map[("1", "Optimized")] == 0
        assert row_map[("2", "Original")] == 0

    def test_empty_distributions(self) -> None:
        rows = build_distribution_overlay_data({}, {})
        assert rows == []

    def test_custom_labels(
        self,
        original_distribution: dict[str, int],
        optimized_distribution: dict[str, int],
    ) -> None:
        rows = build_distribution_overlay_data(
            original_distribution,
            optimized_distribution,
            label_a="Before",
            label_b="After",
        )
        labels = {row["Run"] for row in rows}
        assert labels == {"Before", "After"}
