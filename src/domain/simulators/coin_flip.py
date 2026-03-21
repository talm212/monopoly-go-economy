"""Fully vectorized coin-flip simulation engine.

Uses NumPy for bulk random number generation and array operations,
and Polars for final player-level aggregation.  No Python for-loops
over individual players or interactions.
"""

from __future__ import annotations

import logging

import numpy as np
import polars as pl

from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult

logger = logging.getLogger(__name__)

# Required columns in the player DataFrame
_REQUIRED_COLUMNS = ("user_id", "rolls_sink", "avg_multiplier", "about_to_churn")


class CoinFlipSimulator:
    """Vectorized coin-flip chain simulator.

    The full simulation runs without Python-level loops over players or
    interactions, making it efficient for millions of rows.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        players: pl.DataFrame,
        config: CoinFlipConfig,
        seed: int | None = None,
    ) -> CoinFlipResult:
        """Run the coin-flip simulation for all players.

        Args:
            players: Polars DataFrame with columns user_id, rolls_sink,
                     avg_multiplier, about_to_churn.
            config: A CoinFlipConfig instance.
            seed: Optional RNG seed for reproducibility.

        Returns:
            CoinFlipResult with per-player outcomes and aggregate metrics.
        """
        config.validate()
        errors = self.validate_input(players)
        if errors:
            raise ValueError(f"Invalid player data: {'; '.join(errors)}")
        rng = np.random.default_rng(seed)

        # 1. Compute interactions per player: rolls_sink // avg_multiplier
        players_with_interactions = players.with_columns(
            (pl.col("rolls_sink") // pl.col("avg_multiplier")).cast(pl.Int64).alias("interactions")
        )

        interactions_array = players_with_interactions["interactions"].to_numpy()
        total_interactions = int(interactions_array.sum())

        # Handle the edge case where nobody has any interactions
        if total_interactions == 0:
            return self._build_empty_result(players, config)

        # 2. Build flat arrays: repeat player data by their interaction count
        player_indices = np.repeat(np.arange(len(players)), interactions_array)
        churn_flags = players["about_to_churn"].to_numpy()
        avg_multipliers = players["avg_multiplier"].to_numpy()

        flat_churn = churn_flags[player_indices]
        flat_multipliers = avg_multipliers[player_indices]

        max_s = config.max_successes

        # 3. Generate ALL random numbers at once
        random_values = rng.random((total_interactions, max_s))

        # 4. Build probability matrix: normal probs for non-churn, boosted for churn
        normal_probs = np.array(config.probabilities, dtype=np.float64)
        boosted_probs = np.array(config.get_boosted_probabilities(), dtype=np.float64)

        # prob_matrix shape: (total_interactions, max_successes)
        prob_matrix = np.where(
            flat_churn[:, np.newaxis],
            boosted_probs[np.newaxis, :],
            normal_probs[np.newaxis, :],
        )

        # 5. Compare random values against probabilities → boolean success matrix
        success_matrix = random_values < prob_matrix  # shape: (N, max_s)

        # 6. Find first failure per interaction using cumulative product
        #    cumprod of booleans (treated as 0/1) along axis=1 gives
        #    1 for consecutive successes from the left, 0 after first failure
        cum_successes = np.cumprod(success_matrix.astype(np.int8), axis=1)

        # Success depth per interaction = number of consecutive successes from start
        success_depth = cum_successes.sum(axis=1)  # shape: (N,)

        # 7. Compute points per interaction using cumulative point values
        cum_points = np.cumsum(config.point_values)  # [1, 3, 7, 15, 31] for default
        # Map depth → cumulative points (depth 0 = 0 points)
        # Create lookup: index 0..max_s where index 0 → 0 points
        points_lookup = np.zeros(max_s + 1, dtype=np.float64)
        points_lookup[1:] = cum_points

        interaction_points = points_lookup[success_depth]

        # 8. Multiply points by avg_multiplier
        interaction_points_scaled = interaction_points * flat_multipliers

        # Build success distribution: count how many interactions ended at each depth
        counts = np.bincount(success_depth.astype(int), minlength=config.max_successes + 1)
        success_counts = {depth: int(counts[depth]) for depth in range(config.max_successes + 1)}

        # 9. Aggregate back to player level with Polars
        interaction_df = pl.DataFrame(
            {
                "player_idx": player_indices.astype(np.int64),
                "points": interaction_points_scaled,
            }
        )

        agg_df = interaction_df.group_by("player_idx").agg(
            pl.col("points").sum().alias("total_points"),
            pl.col("points").count().alias("num_interactions"),
        )

        # Join back to the original players (preserving order)
        player_idx_df = pl.DataFrame(
            {
                "player_idx": np.arange(len(players), dtype=np.int64),
            }
        )

        merged = player_idx_df.join(agg_df, on="player_idx", how="left").with_columns(
            pl.col("total_points").fill_null(0.0),
            pl.col("num_interactions").fill_null(0),
        )

        player_results = players.with_columns(
            merged["total_points"].alias("total_points"),
            merged["num_interactions"].alias("num_interactions"),
        )

        total_points = float(player_results["total_points"].sum())
        players_above = int(
            player_results.filter(pl.col("total_points") > config.reward_threshold).height
        )

        return CoinFlipResult(
            player_results=player_results,
            total_interactions=total_interactions,
            success_counts=success_counts,
            total_points=total_points,
            players_above_threshold=players_above,
            threshold=config.reward_threshold,
        )

    def validate_input(self, players: pl.DataFrame) -> list[str]:
        """Validate the player DataFrame and return a list of error messages."""
        errors: list[str] = []
        for col in _REQUIRED_COLUMNS:
            if col not in players.columns:
                errors.append(f"Missing required column: {col}")
        if errors:
            return errors  # Can't validate values if columns are missing

        # avg_multiplier must be positive (non-zero to avoid division by zero)
        if "avg_multiplier" in players.columns:
            non_positive = players.filter(pl.col("avg_multiplier") <= 0).height
            if non_positive > 0:
                errors.append(
                    f"avg_multiplier must be positive (found {non_positive} rows with value <= 0)"
                )
        return errors

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_empty_result(
        self,
        players: pl.DataFrame,
        config: CoinFlipConfig,
    ) -> CoinFlipResult:
        """Build a result when there are zero interactions."""
        player_results = players.with_columns(
            pl.lit(0.0).alias("total_points"),
            pl.lit(0).alias("num_interactions"),
        )
        success_counts = {depth: 0 for depth in range(config.max_successes + 1)}
        return CoinFlipResult(
            player_results=player_results,
            total_interactions=0,
            success_counts=success_counts,
            total_points=0.0,
            players_above_threshold=0,
            threshold=config.reward_threshold,
        )
