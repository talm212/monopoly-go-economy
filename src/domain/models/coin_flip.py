"""Coin flip domain models: configuration and simulation result.

CoinFlipConfig holds the tunable parameters for a coin-flip chain simulation.
CoinFlipResult wraps the per-player outcomes and provides summary accessors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoinFlipConfig:
    """Immutable configuration for one coin-flip simulation run.

    Attributes:
        max_successes: Maximum number of sequential successful flips per interaction.
        probabilities: Success probability for each flip depth (length == max_successes).
        point_values: Points awarded at each flip depth (length == max_successes).
        churn_boost_multiplier: Multiplier applied to probabilities for about-to-churn players.
        reward_threshold: Point threshold for KPI reporting.
    """

    max_successes: int
    probabilities: tuple[float, ...]
    point_values: tuple[float, ...]
    churn_boost_multiplier: float = 1.3
    reward_threshold: float = 100.0

    def validate(self) -> None:
        """Raise ValueError if the configuration is invalid."""
        if self.max_successes <= 0:
            raise ValueError("max_successes must be a positive integer")

        if len(self.probabilities) != self.max_successes:
            raise ValueError(
                f"probabilities length ({len(self.probabilities)}) "
                f"must equal max_successes ({self.max_successes})"
            )

        if len(self.point_values) != self.max_successes:
            raise ValueError(
                f"point_values length ({len(self.point_values)}) "
                f"must equal max_successes ({self.max_successes})"
            )

        for i, p in enumerate(self.probabilities):
            if p < 0.0 or p > 1.0:
                raise ValueError(f"probability at index {i} is {p}; must be in [0, 1]")

        for i, v in enumerate(self.point_values):
            if v < 0.0:
                raise ValueError(f"point_values at index {i} is {v}; must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a plain dictionary."""
        return {
            "max_successes": self.max_successes,
            "probabilities": list(self.probabilities),
            "point_values": list(self.point_values),
            "churn_boost_multiplier": self.churn_boost_multiplier,
            "reward_threshold": self.reward_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoinFlipConfig:
        """Construct a CoinFlipConfig from a plain dictionary."""
        config = cls(
            max_successes=data["max_successes"],
            probabilities=tuple(data["probabilities"]),
            point_values=tuple(data["point_values"]),
            churn_boost_multiplier=data.get("churn_boost_multiplier", 1.3),
            reward_threshold=data.get("reward_threshold", 100.0),
        )
        config.validate()
        return config

    @classmethod
    def from_csv_dict(
        cls,
        csv_data: dict[str, str],
        threshold: float = 100.0,
        churn_boost: float = 1.3,
    ) -> CoinFlipConfig:
        """Parse a config_table.csv key-value mapping into a CoinFlipConfig.

        The CSV format uses keys like ``p_success_1``, ``points_success_1``,
        and ``max_successes``.  Probability values may be percentage strings
        (e.g. ``"60%"``) or plain decimals (e.g. ``"0.6"``).
        """
        max_successes = int(csv_data["max_successes"])

        probabilities: list[float] = []
        for i in range(1, max_successes + 1):
            raw = csv_data[f"p_success_{i}"]
            if raw.endswith("%"):
                probabilities.append(float(raw[:-1]) / 100.0)
            else:
                probabilities.append(float(raw))

        point_values: list[float] = []
        for i in range(1, max_successes + 1):
            point_values.append(float(csv_data[f"points_success_{i}"]))

        config = cls(
            max_successes=max_successes,
            probabilities=tuple(probabilities),
            point_values=tuple(point_values),
            churn_boost_multiplier=churn_boost,
            reward_threshold=threshold,
        )
        config.validate()
        return config

    def get_boosted_probabilities(self) -> list[float]:
        """Return probabilities with churn boost applied, capped at 1.0."""
        return [min(p * self.churn_boost_multiplier, 1.0) for p in self.probabilities]


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------


@dataclass
class CoinFlipResult:
    """Wraps per-player outcomes from a coin-flip simulation run.

    Attributes:
        player_results: Polars DataFrame with per-player aggregated results.
        total_interactions: Total number of coin-flip interactions across all players.
        success_counts: Mapping from success depth (0..max_successes) to count.
        total_points: Sum of all points (after multiplier) across all players.
        players_above_threshold: Number of players whose total_points exceed threshold.
        threshold: The reward threshold used.
    """

    player_results: pl.DataFrame
    total_interactions: int
    success_counts: dict[int, int]
    total_points: float
    players_above_threshold: int
    threshold: float

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a high-level summary as a dictionary."""
        return {
            "total_interactions": self.total_interactions,
            "total_points": self.total_points,
            "players_above_threshold": self.players_above_threshold,
            "threshold": self.threshold,
            "success_distribution": dict(self.success_counts),
        }

    def to_dataframe(self) -> pl.DataFrame:
        """Return the full per-player result DataFrame."""
        return self.player_results

    def get_distribution(self) -> dict[str, int]:
        """Return success depth distribution with string keys."""
        return {str(depth): count for depth, count in sorted(self.success_counts.items())}

    def get_kpi_metrics(self) -> dict[str, float]:
        """Return key performance indicators."""
        points_col = self.player_results["total_points"]
        mean_val = points_col.mean()
        median_val = points_col.median()
        return {
            "mean_points_per_player": float(mean_val) if mean_val is not None else 0.0,
            "median_points_per_player": float(median_val) if median_val is not None else 0.0,
            "total_points": float(self.total_points),
            "pct_above_threshold": (
                float(self.players_above_threshold) / float(len(self.player_results))
                if len(self.player_results) > 0
                else 0.0
            ),
        }
