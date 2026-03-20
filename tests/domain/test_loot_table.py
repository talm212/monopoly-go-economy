"""Tests for loot table domain models and simulator.

Verifies:
- LootTableConfig validation (valid, missing items, negative weights, bad rarity)
- Config serialization roundtrip (to_dict / from_dict)
- LootItem validation edge cases
- Simulator with 100 players: distribution, pity system, guaranteed items
- Empty player DataFrame
- KPI metrics correctness
- ResultsDisplay protocol compliance
- Determinism with seeded RNG
- Protocol conformance (Simulator, SimulationResult, ResultsDisplay)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

from src.domain.models.loot_table import (
    LootItem,
    LootTableConfig,
    LootTableResult,
)
from src.domain.protocols import ResultsDisplay, SimulationResult, Simulator
from src.domain.simulators.loot_table import LootTableSimulator

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_items() -> tuple[LootItem, ...]:
    """Standard 5-item loot table for testing."""
    return (
        LootItem(name="Copper Coin", weight=50.0, rarity="common", value=1.0),
        LootItem(name="Silver Coin", weight=30.0, rarity="uncommon", value=5.0),
        LootItem(name="Gold Coin", weight=12.0, rarity="rare", value=25.0),
        LootItem(name="Diamond", weight=6.0, rarity="epic", value=100.0),
        LootItem(name="Crown Jewel", weight=2.0, rarity="legendary", value=500.0),
    )


def _make_config(
    num_rolls: int = 10,
    pity_threshold: int = 5,
    guaranteed_items: tuple[str, ...] = (),
) -> LootTableConfig:
    return LootTableConfig(
        items=_make_items(),
        num_rolls=num_rolls,
        pity_threshold=pity_threshold,
        guaranteed_items=guaranteed_items,
    )


def _make_players(n: int = 100) -> pl.DataFrame:
    return pl.DataFrame(
        {"user_id": list(range(1, n + 1))}
    )


# ---------------------------------------------------------------------------
# LootItem validation
# ---------------------------------------------------------------------------


class TestLootItemValidation:
    """Verify LootItem rejects invalid definitions."""

    def test_valid_item(self) -> None:
        item = LootItem(name="Sword", weight=10.0, rarity="rare", value=50.0)
        item.validate()  # Should not raise

    def test_empty_name_raises(self) -> None:
        item = LootItem(name="", weight=10.0, rarity="common", value=1.0)
        with pytest.raises(ValueError, match="non-empty"):
            item.validate()

    def test_negative_weight_raises(self) -> None:
        item = LootItem(name="Bad", weight=-1.0, rarity="common", value=1.0)
        with pytest.raises(ValueError, match="weight"):
            item.validate()

    def test_zero_weight_raises(self) -> None:
        item = LootItem(name="Zero", weight=0.0, rarity="common", value=1.0)
        with pytest.raises(ValueError, match="weight"):
            item.validate()

    def test_nan_weight_raises(self) -> None:
        item = LootItem(name="NaN", weight=float("nan"), rarity="common", value=1.0)
        with pytest.raises(ValueError, match="weight"):
            item.validate()

    def test_inf_weight_raises(self) -> None:
        item = LootItem(name="Inf", weight=float("inf"), rarity="common", value=1.0)
        with pytest.raises(ValueError, match="weight"):
            item.validate()

    def test_invalid_rarity_raises(self) -> None:
        item = LootItem(name="Bad", weight=10.0, rarity="mythic", value=1.0)
        with pytest.raises(ValueError, match="rarity"):
            item.validate()

    def test_negative_value_raises(self) -> None:
        item = LootItem(name="Bad", weight=10.0, rarity="common", value=-5.0)
        with pytest.raises(ValueError, match="value"):
            item.validate()

    def test_nan_value_raises(self) -> None:
        item = LootItem(name="NaN", weight=10.0, rarity="common", value=float("nan"))
        with pytest.raises(ValueError, match="value"):
            item.validate()

    def test_item_to_dict_roundtrip(self) -> None:
        item = LootItem(name="Sword", weight=10.0, rarity="rare", value=50.0)
        restored = LootItem.from_dict(item.to_dict())
        assert restored == item


# ---------------------------------------------------------------------------
# LootTableConfig validation
# ---------------------------------------------------------------------------


class TestLootTableConfigValidation:
    """Verify LootTableConfig rejects invalid configurations."""

    def test_valid_config(self) -> None:
        config = _make_config()
        config.validate()  # Should not raise

    def test_empty_items_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            LootTableConfig(items=(), num_rolls=10).validate()

    def test_zero_num_rolls_raises(self) -> None:
        with pytest.raises(ValueError, match="num_rolls"):
            LootTableConfig(items=_make_items(), num_rolls=0).validate()

    def test_negative_num_rolls_raises(self) -> None:
        with pytest.raises(ValueError, match="num_rolls"):
            LootTableConfig(items=_make_items(), num_rolls=-1).validate()

    def test_zero_pity_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="pity_threshold"):
            LootTableConfig(
                items=_make_items(), num_rolls=10, pity_threshold=0
            ).validate()

    def test_duplicate_item_names_raises(self) -> None:
        items = (
            LootItem(name="Coin", weight=50.0, rarity="common", value=1.0),
            LootItem(name="Coin", weight=30.0, rarity="uncommon", value=5.0),
        )
        with pytest.raises(ValueError, match="Duplicate"):
            LootTableConfig(items=items, num_rolls=10).validate()

    def test_invalid_guaranteed_item_raises(self) -> None:
        with pytest.raises(ValueError, match="Guaranteed item"):
            LootTableConfig(
                items=_make_items(),
                num_rolls=10,
                guaranteed_items=("Nonexistent Item",),
            ).validate()

    def test_valid_guaranteed_item(self) -> None:
        config = LootTableConfig(
            items=_make_items(),
            num_rolls=10,
            guaranteed_items=("Gold Coin",),
        )
        config.validate()  # Should not raise


# ---------------------------------------------------------------------------
# Config serialization roundtrip
# ---------------------------------------------------------------------------


class TestLootTableConfigSerialization:
    """Verify to_dict / from_dict roundtrip."""

    def test_roundtrip(self) -> None:
        config = _make_config(num_rolls=15, pity_threshold=8)
        data = config.to_dict()
        restored = LootTableConfig.from_dict(data)

        assert restored.num_rolls == config.num_rolls
        assert restored.pity_threshold == config.pity_threshold
        assert len(restored.items) == len(config.items)
        for orig, rest in zip(config.items, restored.items):
            assert orig == rest

    def test_roundtrip_with_guaranteed_items(self) -> None:
        config = _make_config(guaranteed_items=("Gold Coin",))
        data = config.to_dict()
        restored = LootTableConfig.from_dict(data)
        assert restored.guaranteed_items == ("Gold Coin",)

    def test_from_dict_validates(self) -> None:
        data = {
            "items": [],
            "num_rolls": 10,
        }
        with pytest.raises(ValueError):
            LootTableConfig.from_dict(data)

    def test_to_dict_structure(self) -> None:
        config = _make_config()
        data = config.to_dict()
        assert "items" in data
        assert "num_rolls" in data
        assert "pity_threshold" in data
        assert "guaranteed_items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 5

    def test_schema_returns_config_schema(self) -> None:
        schema = LootTableConfig.schema()
        field_names = [f.name for f in schema.fields]
        assert "num_rolls" in field_names
        assert "pity_threshold" in field_names


# ---------------------------------------------------------------------------
# Simulator — determinism
# ---------------------------------------------------------------------------


class TestLootTableSimulatorDeterminism:
    """Simulation must be fully deterministic when seeded."""

    def test_same_seed_same_results(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)

        result_a = sim.simulate(players, config, seed=42)
        result_b = sim.simulate(players, config, seed=42)

        assert result_a.total_value == result_b.total_value
        assert result_a.total_rolls == result_b.total_rolls
        assert result_a.item_distribution == result_b.item_distribution
        assert result_a.rarity_distribution == result_b.rarity_distribution

    def test_different_seed_different_results(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)

        result_a = sim.simulate(players, config, seed=42)
        result_b = sim.simulate(players, config, seed=999)

        # With different seeds, results should (almost certainly) differ
        assert result_a.total_value != result_b.total_value


# ---------------------------------------------------------------------------
# Simulator — core behavior with 100 players
# ---------------------------------------------------------------------------


class TestLootTableSimulatorCore:
    """Verify simulation produces correct results for 100 players."""

    def test_total_rolls_correct(self) -> None:
        sim = LootTableSimulator()
        config = _make_config(num_rolls=10)
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        assert result.total_rolls == 1000  # 100 players * 10 rolls

    def test_item_distribution_sums_to_total_rolls(self) -> None:
        sim = LootTableSimulator()
        config = _make_config(num_rolls=10)
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        assert sum(result.item_distribution.values()) == result.total_rolls

    def test_rarity_distribution_sums_to_total_rolls(self) -> None:
        sim = LootTableSimulator()
        config = _make_config(num_rolls=10)
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        assert sum(result.rarity_distribution.values()) == result.total_rolls

    def test_player_results_has_expected_columns(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        df = result.player_results
        assert "user_id" in df.columns
        assert "items_received" in df.columns
        assert "total_value" in df.columns
        assert "rare_count" in df.columns
        assert "legendary_count" in df.columns

    def test_player_count_matches(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        assert result.player_results.height == 100

    def test_total_value_equals_player_sum(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        player_sum = result.player_results["total_value"].sum()
        assert result.total_value == pytest.approx(player_sum)

    def test_all_values_non_negative(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)
        assert (result.player_results["total_value"] >= 0.0).all()
        assert (result.player_results["rare_count"] >= 0).all()

    def test_weighted_distribution_favors_common(self) -> None:
        """With standard weights, common items should appear most often."""
        sim = LootTableSimulator()
        config = _make_config(num_rolls=50, pity_threshold=100)  # High pity to avoid interference
        players = _make_players(200)
        result = sim.simulate(players, config, seed=42)
        dist = result.item_distribution
        assert dist["Copper Coin"] > dist["Crown Jewel"]


# ---------------------------------------------------------------------------
# Simulator — pity system
# ---------------------------------------------------------------------------


class TestLootTableSimulatorPity:
    """Verify the pity system guarantees rare+ drops."""

    def test_pity_ensures_rare_drops(self) -> None:
        """With a low pity threshold, every player should get at least one rare+ item."""
        # Use only common items to force pity triggers
        items = (
            LootItem(name="Junk", weight=98.0, rarity="common", value=1.0),
            LootItem(name="Gem", weight=2.0, rarity="rare", value=100.0),
        )
        config = LootTableConfig(
            items=items,
            num_rolls=20,
            pity_threshold=3,
        )
        sim = LootTableSimulator()
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)

        # Every player should have at least one rare item due to pity
        assert (result.player_results["rare_count"] > 0).all()

    def test_high_pity_threshold_no_forced_drops(self) -> None:
        """With pity threshold >= num_rolls, pity never triggers."""
        items = (
            LootItem(name="Junk", weight=100.0, rarity="common", value=1.0),
            LootItem(name="Gem", weight=0.001, rarity="rare", value=100.0),
        )
        config = LootTableConfig(
            items=items,
            num_rolls=5,
            pity_threshold=100,
        )
        sim = LootTableSimulator()
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)

        # With 99.999% common and only 5 rolls, most players get 0 rare items
        # At least some players should have 0 rare items
        zero_rare = result.player_results.filter(pl.col("rare_count") == 0).height
        assert zero_rare > 0

    def test_pity_resets_after_rare_drop(self) -> None:
        """Verify pity counter resets after getting a rare+ item."""
        # 100% common except 1 rare item with tiny weight
        items = (
            LootItem(name="Junk", weight=999.0, rarity="common", value=1.0),
            LootItem(name="Gem", weight=1.0, rarity="rare", value=100.0),
        )
        config = LootTableConfig(
            items=items,
            num_rolls=30,
            pity_threshold=5,
        )
        sim = LootTableSimulator()
        players = _make_players(100)
        result = sim.simulate(players, config, seed=42)

        # With 30 rolls and pity every 5, players should get multiple rare items
        # At least the average should be > 1
        mean_rare = result.player_results["rare_count"].mean()
        assert mean_rare > 1.0  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Simulator — guaranteed items
# ---------------------------------------------------------------------------


class TestLootTableSimulatorGuaranteed:
    """Verify guaranteed items are applied correctly."""

    def test_guaranteed_item_on_first_roll(self) -> None:
        """Every player should receive the guaranteed item."""
        import json

        sim = LootTableSimulator()
        config = _make_config(num_rolls=5, guaranteed_items=("Crown Jewel",))
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)

        # Every player should have at least one Crown Jewel
        for row in result.player_results.iter_rows(named=True):
            items = json.loads(row["items_received"])
            assert "Crown Jewel" in items, f"Player {row['user_id']} missing guaranteed item"

    def test_multiple_guaranteed_items(self) -> None:
        import json

        sim = LootTableSimulator()
        config = _make_config(
            num_rolls=5,
            guaranteed_items=("Crown Jewel", "Diamond"),
        )
        players = _make_players(30)
        result = sim.simulate(players, config, seed=42)

        for row in result.player_results.iter_rows(named=True):
            items = json.loads(row["items_received"])
            assert "Crown Jewel" in items
            assert "Diamond" in items


# ---------------------------------------------------------------------------
# Simulator — empty DataFrame
# ---------------------------------------------------------------------------


class TestLootTableSimulatorEmpty:
    """Verify correct handling of empty input."""

    def test_empty_players(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        empty_players = pl.DataFrame(
            {"user_id": pl.Series([], dtype=pl.Int64)}
        )
        result = sim.simulate(empty_players, config, seed=42)

        assert result.total_rolls == 0
        assert result.total_value == 0.0
        assert result.player_results.height == 0


# ---------------------------------------------------------------------------
# Simulator — input validation
# ---------------------------------------------------------------------------


class TestLootTableSimulatorValidation:
    """Verify input validation catches bad DataFrames."""

    def test_missing_user_id_column(self) -> None:
        sim = LootTableSimulator()
        df = pl.DataFrame({"name": ["Alice"]})
        errors = sim.validate_input(df)
        assert any("user_id" in e for e in errors)

    def test_valid_input_returns_no_errors(self) -> None:
        sim = LootTableSimulator()
        df = pl.DataFrame({"user_id": [1, 2, 3]})
        errors = sim.validate_input(df)
        assert errors == []

    def test_simulate_raises_on_invalid_input(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        bad_df = pl.DataFrame({"name": ["Alice"]})
        with pytest.raises(ValueError, match="Invalid player data"):
            sim.simulate(bad_df, config, seed=42)


# ---------------------------------------------------------------------------
# KPI metrics
# ---------------------------------------------------------------------------


class TestLootTableKPIMetrics:
    """Verify KPI metrics are computed correctly."""

    def test_kpi_metrics_keys(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)
        kpis = result.get_kpi_metrics()
        assert "mean_value_per_player" in kpis
        assert "median_value_per_player" in kpis
        assert "total_value" in kpis
        assert "pct_got_legendary" in kpis

    def test_kpi_metrics_types(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)
        kpis = result.get_kpi_metrics()
        assert all(isinstance(v, float) for v in kpis.values())

    def test_kpi_total_value_matches_result(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)
        kpis = result.get_kpi_metrics()
        assert kpis["total_value"] == pytest.approx(result.total_value)

    def test_kpi_mean_is_total_over_count(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)
        kpis = result.get_kpi_metrics()
        expected_mean = result.total_value / 50
        assert kpis["mean_value_per_player"] == pytest.approx(expected_mean)

    def test_kpi_pct_legendary_in_range(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)
        result = sim.simulate(players, config, seed=42)
        kpis = result.get_kpi_metrics()
        assert 0.0 <= kpis["pct_got_legendary"] <= 1.0

    def test_kpi_empty_dataframe(self) -> None:
        empty_df = pl.DataFrame(
            {
                "user_id": pl.Series([], dtype=pl.Int64),
                "items_received": pl.Series([], dtype=pl.Utf8),
                "total_value": pl.Series([], dtype=pl.Float64),
                "rare_count": pl.Series([], dtype=pl.Int64),
                "legendary_count": pl.Series([], dtype=pl.Int64),
            }
        )
        result = LootTableResult(
            player_results=empty_df,
            total_rolls=0,
            item_distribution={},
            rarity_distribution={},
            total_value=0.0,
        )
        kpis = result.get_kpi_metrics()
        assert kpis["mean_value_per_player"] == 0.0
        assert kpis["median_value_per_player"] == 0.0
        assert kpis["total_value"] == 0.0
        assert kpis["pct_got_legendary"] == 0.0


# ---------------------------------------------------------------------------
# ResultsDisplay protocol compliance
# ---------------------------------------------------------------------------


class TestLootTableResultsDisplay:
    """Verify LootTableResult satisfies the ResultsDisplay protocol."""

    @pytest.fixture
    def result(self) -> LootTableResult:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(50)
        return sim.simulate(players, config, seed=42)

    def test_implements_results_display_protocol(self, result: LootTableResult) -> None:
        assert isinstance(result, ResultsDisplay)

    def test_get_kpi_cards_returns_four_cards(self, result: LootTableResult) -> None:
        cards = result.get_kpi_cards()
        assert len(cards) == 4
        expected_labels = {
            "Mean Value / Player",
            "Median Value / Player",
            "Total Value",
            "% Got Legendary",
        }
        assert set(cards.keys()) == expected_labels

    def test_get_kpi_cards_includes_help_text(self, result: LootTableResult) -> None:
        cards = result.get_kpi_cards()
        for label, (value, help_text) in cards.items():
            assert isinstance(help_text, str)
            assert len(help_text) > 0, f"Help text for '{label}' should not be empty"

    def test_get_distribution_returns_str_int_dict(self, result: LootTableResult) -> None:
        dist = result.get_distribution()
        assert isinstance(dist, dict)
        assert all(isinstance(k, str) for k in dist)
        assert all(isinstance(v, int) for v in dist.values())

    def test_get_segments_returns_none(self, result: LootTableResult) -> None:
        """Loot table has no segment split — should return None."""
        segments = result.get_segments()
        assert segments is None

    def test_get_dataframe_returns_polars_df(self, result: LootTableResult) -> None:
        df = result.get_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert "user_id" in df.columns

    def test_to_summary_dict_contains_keys(self, result: LootTableResult) -> None:
        summary = result.to_summary_dict()
        assert "total_rolls" in summary
        assert "total_value" in summary
        assert "item_distribution" in summary
        assert "rarity_distribution" in summary


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestLootTableProtocolConformance:
    """Verify protocol contract compliance."""

    def test_simulator_implements_protocol(self) -> None:
        sim = LootTableSimulator()
        assert isinstance(sim, Simulator)

    def test_result_implements_simulation_result(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(10)
        result = sim.simulate(players, config, seed=42)
        assert isinstance(result, SimulationResult)

    def test_result_implements_results_display(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(10)
        result = sim.simulate(players, config, seed=42)
        assert isinstance(result, ResultsDisplay)


# ---------------------------------------------------------------------------
# to_analysis_context
# ---------------------------------------------------------------------------


class TestLootTableAnalysisContext:
    """Verify to_analysis_context produces correct FeatureAnalysisContext."""

    def test_returns_feature_analysis_context(self) -> None:
        from src.domain.protocols import FeatureAnalysisContext

        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(20)
        result = sim.simulate(players, config, seed=42)
        ctx = result.to_analysis_context(config)
        assert isinstance(ctx, FeatureAnalysisContext)

    def test_feature_name_is_loot_table(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(20)
        result = sim.simulate(players, config, seed=42)
        ctx = result.to_analysis_context(config)
        assert ctx.feature_name == "loot_table"

    def test_config_matches_to_dict(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(20)
        result = sim.simulate(players, config, seed=42)
        ctx = result.to_analysis_context(config)
        assert ctx.config == config.to_dict()

    def test_segment_data_is_none(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(20)
        result = sim.simulate(players, config, seed=42)
        ctx = result.to_analysis_context(config)
        assert ctx.segment_data is None

    def test_kpi_metrics_present(self) -> None:
        sim = LootTableSimulator()
        config = _make_config()
        players = _make_players(20)
        result = sim.simulate(players, config, seed=42)
        ctx = result.to_analysis_context(config)
        assert "mean_value_per_player" in ctx.kpi_metrics
        assert "total_value" in ctx.kpi_metrics
