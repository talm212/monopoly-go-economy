"""Vectorized loot table simulation engine.

Uses NumPy for bulk random item selection with weights, and Polars for
final player-level aggregation. Implements a pity system that guarantees
rare+ drops after N consecutive rolls without one, and supports
guaranteed items on first roll.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import polars as pl

from src.domain.models.loot_table import (
    RARE_PLUS_RARITIES,
    LootTableConfig,
    LootTableResult,
)

logger = logging.getLogger(__name__)

# Required columns in the player DataFrame
_REQUIRED_COLUMNS = ("user_id",)


class LootTableSimulator:
    """Vectorized loot table simulator with pity system.

    Rolls items from a weighted pool for each player, tracking pity
    counters to guarantee rare+ drops after a configurable threshold.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        players: pl.DataFrame,
        config: LootTableConfig | Any,
        seed: int | None = None,
    ) -> LootTableResult:
        """Run the loot table simulation for all players.

        Args:
            players: Polars DataFrame with at least a ``user_id`` column.
            config: A LootTableConfig instance.
            seed: Optional RNG seed for reproducibility.

        Returns:
            LootTableResult with per-player outcomes and aggregate metrics.
        """
        config.validate()
        errors = self.validate_input(players)
        if errors:
            raise ValueError(f"Invalid player data: {'; '.join(errors)}")

        rng = np.random.default_rng(seed)
        num_players = players.height

        if num_players == 0:
            return self._build_empty_result(players, config)

        num_rolls = config.num_rolls
        items = config.items
        num_items = len(items)

        # Pre-compute item metadata arrays
        item_names = [item.name for item in items]
        item_values = np.array([item.value for item in items], dtype=np.float64)
        item_rarities = [item.rarity for item in items]
        item_weights = np.array([item.weight for item in items], dtype=np.float64)

        # Boolean mask: which items are rare+
        is_rare_plus = np.array(
            [r in RARE_PLUS_RARITIES for r in item_rarities], dtype=bool
        )

        # Identify rare+ item indices and their weights for pity rolls
        rare_plus_indices = np.where(is_rare_plus)[0]
        has_rare_plus_items = len(rare_plus_indices) > 0

        if has_rare_plus_items:
            rare_plus_weights = item_weights[rare_plus_indices]
            rare_plus_probs = rare_plus_weights / rare_plus_weights.sum()

        # Normalize weights for standard rolls
        standard_probs = item_weights / item_weights.sum()

        # Build guaranteed item indices
        guaranteed_indices: list[int] = []
        name_to_idx = {name: i for i, name in enumerate(item_names)}
        for gname in config.guaranteed_items:
            guaranteed_indices.append(name_to_idx[gname])

        # --- Simulation ---
        # result_items[p, r] = index into items array for player p, roll r
        result_items = np.empty((num_players, num_rolls), dtype=np.int64)

        # Generate all standard rolls at once (vectorized)
        # Shape: (num_players, num_rolls)
        all_rolls = rng.choice(
            num_items,
            size=(num_players, num_rolls),
            p=standard_probs,
        )
        result_items[:] = all_rolls

        # Apply guaranteed items on first roll(s)
        # Guaranteed items replace the first len(guaranteed_indices) rolls
        for gi, item_idx in enumerate(guaranteed_indices):
            if gi < num_rolls:
                result_items[:, gi] = item_idx

        # Apply pity system: scan each player's rolls and force rare+ when needed
        # This requires a sequential scan per player due to state (pity counter),
        # but we vectorize the inner logic where possible.
        if has_rare_plus_items and config.pity_threshold < num_rolls:
            self._apply_pity_system(
                result_items=result_items,
                is_rare_plus=is_rare_plus,
                rare_plus_indices=rare_plus_indices,
                rare_plus_probs=rare_plus_probs,
                pity_threshold=config.pity_threshold,
                guaranteed_count=len(guaranteed_indices),
                rng=rng,
            )

        # --- Aggregation ---
        # Compute per-player stats using vectorized operations
        # Total value per player
        flat_values = item_values[result_items.ravel()]
        player_total_values = flat_values.reshape(num_players, num_rolls).sum(axis=1)

        # Rare count per player (rare + epic + legendary)
        flat_is_rare = is_rare_plus[result_items.ravel()]
        player_rare_counts = flat_is_rare.reshape(num_players, num_rolls).sum(axis=1)

        # Legendary count per player
        is_legendary = np.array(
            [r == "legendary" for r in item_rarities], dtype=bool
        )
        flat_is_legendary = is_legendary[result_items.ravel()]
        player_legendary_counts = flat_is_legendary.reshape(num_players, num_rolls).sum(axis=1)

        # Build items_received JSON strings per player
        items_received_strs = self._build_items_received_json(
            result_items, item_names, num_players, num_rolls
        )

        # Build item distribution (global)
        flat_items = result_items.ravel()
        item_counts = np.bincount(flat_items, minlength=num_items)
        item_distribution = {
            item_names[i]: int(item_counts[i]) for i in range(num_items)
        }

        # Build rarity distribution (global)
        rarity_distribution: dict[str, int] = {}
        for i, rarity in enumerate(item_rarities):
            rarity_distribution[rarity] = rarity_distribution.get(rarity, 0) + int(
                item_counts[i]
            )

        # Build player results DataFrame
        player_results = players.with_columns(
            pl.Series("items_received", items_received_strs, dtype=pl.String),
            pl.Series("total_value", player_total_values, dtype=pl.Float64),
            pl.Series("rare_count", player_rare_counts.astype(np.int64), dtype=pl.Int64),
            pl.Series("legendary_count", player_legendary_counts.astype(np.int64), dtype=pl.Int64),
        )

        total_value = float(player_total_values.sum())
        total_rolls = num_players * num_rolls

        return LootTableResult(
            player_results=player_results,
            total_rolls=total_rolls,
            item_distribution=item_distribution,
            rarity_distribution=rarity_distribution,
            total_value=total_value,
        )

    def validate_input(self, players: pl.DataFrame) -> list[str]:
        """Validate the player DataFrame and return a list of error messages."""
        errors: list[str] = []
        for col in _REQUIRED_COLUMNS:
            if col not in players.columns:
                errors.append(f"Missing required column: {col}")
        return errors

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_pity_system(
        self,
        result_items: np.ndarray,
        is_rare_plus: np.ndarray,
        rare_plus_indices: np.ndarray,
        rare_plus_probs: np.ndarray,
        pity_threshold: int,
        guaranteed_count: int,
        rng: np.random.Generator,
    ) -> None:
        """Apply pity system in-place to result_items.

        For each player, tracks consecutive rolls without a rare+ item.
        When the counter reaches pity_threshold, the next roll is forced
        to a rare+ item (weighted by their relative weights).

        Vectorized across players: iterates over rolls (columns) and
        processes all players simultaneously using NumPy boolean masks.
        This reduces Python loop iterations from O(players * rolls) to
        O(rolls).
        """
        num_players, num_rolls = result_items.shape

        # Start scanning after guaranteed items (they don't count for pity)
        start_roll = guaranteed_count

        # Per-player pity counter — vectorized across all players
        pity_counters = np.zeros(num_players, dtype=np.int64)

        for r in range(start_roll, num_rolls):
            # Identify players that hit the pity threshold
            pity_mask = pity_counters >= pity_threshold

            if pity_mask.any():
                # Force rare+ drops for pity-triggered players (all at once)
                num_pity = int(pity_mask.sum())
                forced_items = rng.choice(
                    rare_plus_indices, size=num_pity, p=rare_plus_probs
                )
                result_items[pity_mask, r] = forced_items
                pity_counters[pity_mask] = 0

            # Check which non-pity players got a rare+ item naturally
            non_pity_mask = ~pity_mask
            got_rare = non_pity_mask & is_rare_plus[result_items[:, r]]
            pity_counters[got_rare] = 0

            # Increment counter for non-pity players who did NOT get rare+
            no_rare = non_pity_mask & ~is_rare_plus[result_items[:, r]]
            pity_counters[no_rare] += 1

    def _build_items_received_json(
        self,
        result_items: np.ndarray,
        item_names: list[str],
        num_players: int,
        num_rolls: int,
    ) -> list[str]:
        """Build JSON strings of item counts per player.

        Uses np.bincount per row to eliminate the inner Python loop over
        rolls, reducing from O(players * rolls) to O(players) Python
        iterations with vectorized counting.
        """
        num_items = len(item_names)
        items_received_strs: list[str] = []
        for p in range(num_players):
            bin_counts = np.bincount(result_items[p], minlength=num_items)
            counts = {
                item_names[i]: int(bin_counts[i])
                for i in range(num_items)
                if bin_counts[i] > 0
            }
            items_received_strs.append(json.dumps(counts))
        return items_received_strs

    def _build_empty_result(
        self,
        players: pl.DataFrame,
        config: LootTableConfig,
    ) -> LootTableResult:
        """Build a result when there are zero players."""
        player_results = players.with_columns(
            pl.lit("{}").alias("items_received"),
            pl.lit(0.0).alias("total_value"),
            pl.lit(0).cast(pl.Int64).alias("rare_count"),
            pl.lit(0).cast(pl.Int64).alias("legendary_count"),
        )
        return LootTableResult(
            player_results=player_results,
            total_rolls=0,
            item_distribution={item.name: 0 for item in config.items},
            rarity_distribution={},
            total_value=0.0,
        )
