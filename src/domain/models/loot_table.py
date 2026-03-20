"""Loot table domain models: configuration and simulation result.

LootTableConfig holds the tunable parameters for a weighted loot pool simulation
with rarity tiers and a pity system. LootTableResult wraps the per-player
outcomes and provides summary accessors following the ResultsDisplay protocol.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Any

import polars as pl

from src.domain.protocols import (
    ConfigField,
    ConfigFieldType,
    ConfigSchema,
    FeatureAnalysisContext,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_RARITIES = frozenset({"common", "uncommon", "rare", "epic", "legendary"})
RARE_PLUS_RARITIES = frozenset({"rare", "epic", "legendary"})

# ---------------------------------------------------------------------------
# KPI help text constants (used by ResultsDisplay.get_kpi_cards)
# ---------------------------------------------------------------------------

_KPI_HELP: dict[str, str] = {
    "Mean Value / Player": (
        "**Calculation:** sum(total_value) / count(players)\n\n"
        "**Parameters:**\n"
        "- total_value per player = sum of value for all items received\n"
        "- Each roll picks one item from the weighted loot pool\n"
        "- Pity system guarantees rare+ items after N unlucky rolls"
    ),
    "Median Value / Player": (
        "**Calculation:** middle value when all players' total_value are sorted\n\n"
        "Less sensitive to outliers than the mean.\n"
        "If mean >> median, a few players received disproportionately valuable loot."
    ),
    "Total Value": (
        "**Calculation:** sum(total_value) across all players\n\n"
        "**Parameters:**\n"
        "- Reflects the total economy output of the loot table simulation\n"
        "- Includes guaranteed items and pity-system forced drops"
    ),
    "% Got Legendary": (
        "**Calculation:** count(players with at least 1 legendary) "
        "/ count(players) * 100\n\n"
        "**Parameters:**\n"
        "- Tracks what fraction of the player base obtained legendary-tier loot\n"
        "- Higher values may indicate the pity system is too generous"
    ),
}


# ---------------------------------------------------------------------------
# Loot item
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LootItem:
    """A single item in the loot table.

    Attributes:
        name: Unique item identifier.
        weight: Relative probability weight (must be positive).
        rarity: Rarity tier — one of common, uncommon, rare, epic, legendary.
        value: Numeric value of the item for economy tracking.
    """

    name: str
    weight: float
    rarity: str
    value: float

    def validate(self) -> None:
        """Raise ValueError if the item definition is invalid."""
        if not self.name:
            raise ValueError("Item name must be non-empty")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError(
                f"Item '{self.name}' has weight {self.weight}; must be a finite positive number"
            )
        if self.rarity not in VALID_RARITIES:
            raise ValueError(
                f"Item '{self.name}' has rarity '{self.rarity}'; "
                f"must be one of {sorted(VALID_RARITIES)}"
            )
        if not math.isfinite(self.value) or self.value < 0.0:
            raise ValueError(
                f"Item '{self.name}' has value {self.value}; must be a finite non-negative number"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "name": self.name,
            "weight": self.weight,
            "rarity": self.rarity,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LootItem:
        """Construct a LootItem from a plain dictionary."""
        return cls(
            name=data["name"],
            weight=float(data["weight"]),
            rarity=data["rarity"],
            value=float(data["value"]),
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LootTableConfig:
    """Immutable configuration for one loot table simulation run.

    Attributes:
        items: Tuple of LootItem definitions forming the loot pool.
        num_rolls: Number of rolls each player gets.
        pity_threshold: After this many rolls without rare+ drop, guarantee one.
        guaranteed_items: Item names guaranteed on the first roll.
    """

    items: tuple[LootItem, ...]
    num_rolls: int
    pity_threshold: int = 10
    guaranteed_items: tuple[str, ...] = ()

    def validate(self) -> None:
        """Raise ValueError if the configuration is invalid."""
        if not self.items:
            raise ValueError("items must contain at least one LootItem")

        if self.num_rolls <= 0:
            raise ValueError("num_rolls must be a positive integer")

        if self.pity_threshold <= 0:
            raise ValueError("pity_threshold must be a positive integer")

        # Validate individual items
        names_seen: set[str] = set()
        for item in self.items:
            item.validate()
            if item.name in names_seen:
                raise ValueError(f"Duplicate item name: '{item.name}'")
            names_seen.add(item.name)

        # Validate guaranteed items reference existing item names
        item_names = {item.name for item in self.items}
        for gname in self.guaranteed_items:
            if gname not in item_names:
                raise ValueError(
                    f"Guaranteed item '{gname}' is not in the items list"
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a plain dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "num_rolls": self.num_rolls,
            "pity_threshold": self.pity_threshold,
            "guaranteed_items": list(self.guaranteed_items),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LootTableConfig:
        """Construct a LootTableConfig from a plain dictionary."""
        items = tuple(LootItem.from_dict(d) for d in data["items"])
        config = cls(
            items=items,
            num_rolls=data["num_rolls"],
            pity_threshold=data.get("pity_threshold", 10),
            guaranteed_items=tuple(data.get("guaranteed_items", ())),
        )
        config.validate()
        return config

    @classmethod
    def schema(cls) -> ConfigSchema:
        """Return a ConfigSchema describing the loot table configuration fields."""
        fields: list[ConfigField] = [
            ConfigField(
                name="num_rolls",
                display_name="Rolls per Player",
                field_type=ConfigFieldType.INTEGER,
                default=10,
                min_value=1,
                max_value=100,
                help_text="Number of loot rolls each player receives",
            ),
            ConfigField(
                name="pity_threshold",
                display_name="Pity Threshold",
                field_type=ConfigFieldType.INTEGER,
                default=10,
                min_value=1,
                max_value=50,
                help_text="After N rolls without rare+ drop, guarantee one on the next roll",
            ),
        ]
        return ConfigSchema(fields=fields)


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------


@dataclass
class LootTableResult:
    """Wraps per-player outcomes from a loot table simulation run.

    Attributes:
        player_results: Polars DataFrame with per-player aggregated results
            (user_id, items_received, total_value, rare_count).
        total_rolls: Total number of loot rolls across all players.
        item_distribution: Mapping from item name to total drop count.
        rarity_distribution: Mapping from rarity tier to total drop count.
        total_value: Sum of all item values across all players.
    """

    player_results: pl.DataFrame
    total_rolls: int
    item_distribution: dict[str, int]
    rarity_distribution: dict[str, int]
    total_value: float

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a high-level summary as a dictionary."""
        return {
            "total_rolls": self.total_rolls,
            "total_value": self.total_value,
            "item_distribution": dict(self.item_distribution),
            "rarity_distribution": dict(self.rarity_distribution),
        }

    def to_dataframe(self) -> pl.DataFrame:
        """Return the full per-player result DataFrame."""
        return self.player_results

    def get_distribution(self) -> dict[str, int]:
        """Return rarity distribution with string keys."""
        return {rarity: count for rarity, count in sorted(self.rarity_distribution.items())}

    def get_kpi_metrics(self) -> dict[str, float]:
        """Return key performance indicators."""
        if self.player_results.height == 0:
            return {
                "mean_value_per_player": 0.0,
                "median_value_per_player": 0.0,
                "total_value": 0.0,
                "pct_got_legendary": 0.0,
            }

        value_col = self.player_results["total_value"]
        mean_val = value_col.mean()
        median_val = value_col.median()

        # Count players who got at least one legendary
        legendary_col = self.player_results["legendary_count"]
        players_with_legendary = int(
            self.player_results.filter(pl.col("legendary_count") > 0).height
        )

        return {
            "mean_value_per_player": float(mean_val) if mean_val is not None else 0.0,
            "median_value_per_player": float(median_val) if median_val is not None else 0.0,
            "total_value": float(self.total_value),
            "pct_got_legendary": (
                float(players_with_legendary) / float(self.player_results.height)
                if self.player_results.height > 0
                else 0.0
            ),
        }

    # ------------------------------------------------------------------
    # ResultsDisplay protocol methods
    # ------------------------------------------------------------------

    def get_kpi_cards(self) -> dict[str, tuple[float | int, str]]:
        """Return KPI card data as ``{label: (value, help_text)}``."""
        raw = self.get_kpi_metrics()
        return {
            "Mean Value / Player": (
                raw["mean_value_per_player"],
                _KPI_HELP["Mean Value / Player"],
            ),
            "Median Value / Player": (
                raw["median_value_per_player"],
                _KPI_HELP["Median Value / Player"],
            ),
            "Total Value": (
                raw["total_value"],
                _KPI_HELP["Total Value"],
            ),
            "% Got Legendary": (
                round(raw["pct_got_legendary"] * 100, 2),
                _KPI_HELP["% Got Legendary"],
            ),
        }

    def get_segments(self) -> dict[str, dict[str, float]] | None:
        """Return rarity tier segment breakdowns, or ``None``.

        Since loot table does not have a natural churn split, returns None.
        Future versions could segment by player tier or activity level.
        """
        return None

    def get_dataframe(self) -> pl.DataFrame:
        """Return the full result DataFrame for download / display."""
        return self.player_results

    def to_analysis_context(self, config: LootTableConfig) -> FeatureAnalysisContext:
        """Build a FeatureAnalysisContext with loot-table-specific data.

        Args:
            config: The LootTableConfig used for this simulation run.

        Returns:
            A fully populated FeatureAnalysisContext.
        """
        result_summary = self.to_summary_dict()
        kpi_metrics = self.get_kpi_metrics()
        result_summary.update(kpi_metrics)

        return FeatureAnalysisContext(
            feature_name="loot_table",
            result_summary=result_summary,
            distribution=self.get_distribution(),
            config=config.to_dict(),
            kpi_metrics=kpi_metrics,
            segment_data=None,
        )
