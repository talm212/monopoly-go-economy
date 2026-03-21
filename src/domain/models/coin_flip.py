"""Coin flip domain models: configuration and simulation result.

CoinFlipConfig holds the tunable parameters for a coin-flip chain simulation.
CoinFlipResult wraps the per-player outcomes and provides summary accessors.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import polars as pl

from src.domain.protocols import ConfigField, ConfigFieldType, ConfigSchema, FeatureAnalysisContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KPI help text constants (used by ResultsDisplay.get_kpi_cards)
# ---------------------------------------------------------------------------

_KPI_HELP: dict[str, str] = {
    "Total Interactions": (
        "**total_roll_interactions** -- total interactions simulated.\n\n"
        "**Calculation:** sum(floor(rolls_sink / avg_multiplier)) for each player.\n"
        "Each interaction triggers one coin-flip chain."
    ),
    "Total Points": (
        "**total_points** -- total points awarded across all players.\n\n"
        "**Calculation:** sum over all players of "
        "(sum over interactions of cumulative points at success depth * avg_multiplier)."
    ),
    "Players Above Threshold": (
        "**players_above_threshold** -- players whose total points exceed "
        "the reward threshold.\n\n"
        "**Calculation:** count(players where total_points > reward_threshold).\n"
        "Adjust reward_threshold in the Simulation Settings tab."
    ),
}

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

    def __post_init__(self) -> None:
        self.validate()

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
            if not math.isfinite(p) or p < 0.0 or p > 1.0:
                raise ValueError(f"probability at index {i} is {p}; must be a finite number in [0, 1]")

        for i, v in enumerate(self.point_values):
            if not math.isfinite(v) or v < 0.0:
                raise ValueError(f"point_values at index {i} is {v}; must be a finite non-negative number")

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

        # Pick up reward_threshold / churn_boost_multiplier from the dict
        # if present (e.g. when edited in the UI), else use function args.
        if "reward_threshold" in csv_data:
            threshold = float(csv_data["reward_threshold"])
        if "churn_boost_multiplier" in csv_data:
            churn_boost = float(csv_data["churn_boost_multiplier"])

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

    @classmethod
    def schema(cls, max_successes: int = 5) -> ConfigSchema:
        """Return a ConfigSchema describing the coin-flip configuration fields.

        Args:
            max_successes: Number of flip depths to include in the schema.
                Defaults to 5 (the standard coin-flip depth).
        """
        fields: list[ConfigField] = []
        for i in range(1, max_successes + 1):
            fields.append(
                ConfigField(
                    name=f"p_success_{i}",
                    display_name=f"P(Success {i})",
                    field_type=ConfigFieldType.PERCENTAGE,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    help_text=f"Probability of success at flip depth {i}",
                    group="probabilities",
                )
            )
            fields.append(
                ConfigField(
                    name=f"points_success_{i}",
                    display_name=f"Points (Depth {i})",
                    field_type=ConfigFieldType.INTEGER,
                    default=1,
                    min_value=0,
                    help_text=f"Points awarded for success at depth {i}",
                    group="points",
                )
            )
        fields.append(
            ConfigField(
                name="max_successes",
                display_name="Max Successes",
                field_type=ConfigFieldType.INTEGER,
                default=5,
                min_value=1,
                max_value=10,
                help_text="Maximum number of sequential successful flips per interaction",
            )
        )
        return ConfigSchema(fields=fields)


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

    # ------------------------------------------------------------------
    # ResultsDisplay protocol methods
    # ------------------------------------------------------------------

    def get_kpi_cards(self) -> dict[str, tuple[float | int, str]]:
        """Return KPI card data as ``{label: (value, help_text)}``.

        Matches the required output from the Tech Test spec:
        total_roll_interactions, total_points, players_above_threshold.
        Success counts are shown in the distribution chart, not as KPI cards.
        """
        return {
            "Total Interactions": (
                self.total_interactions,
                _KPI_HELP["Total Interactions"],
            ),
            "Total Points": (
                self.total_points,
                _KPI_HELP["Total Points"],
            ),
            "Players Above Threshold": (
                self.players_above_threshold,
                _KPI_HELP["Players Above Threshold"],
            ),
        }

    def get_segments(self) -> dict[str, dict[str, float]] | None:
        """Return churn vs non-churn segment breakdowns, or ``None``."""
        if "about_to_churn" not in self.player_results.columns:
            return None

        segments: dict[str, dict[str, float]] = {}
        churn_df = self.player_results.filter(pl.col("about_to_churn"))
        non_churn_df = self.player_results.filter(~pl.col("about_to_churn"))

        for label, seg_df in (("churn", churn_df), ("non-churn", non_churn_df)):
            if seg_df.height == 0:
                segments[label] = {
                    "Player Count": 0.0,
                    "Avg Points / Player": 0.0,
                    "Median Points / Player": 0.0,
                    "Total Points": 0.0,
                }
            else:
                pts = seg_df["total_points"]
                segments[label] = {
                    "Player Count": float(seg_df.height),
                    "Avg Points / Player": float(pts.mean() or 0.0),
                    "Median Points / Player": float(pts.median() or 0.0),
                    "Total Points": float(pts.sum() or 0.0),
                }
        return segments

    def get_dataframe(self) -> pl.DataFrame:
        """Return the full result DataFrame for download / display."""
        return self.player_results

    def to_analysis_context(self, config: CoinFlipConfig) -> FeatureAnalysisContext:
        """Build a FeatureAnalysisContext with coin-flip-specific data.

        Encapsulates the context-building logic (summary, KPIs, churn segments)
        that was previously scattered across the UI layer.

        Args:
            config: The CoinFlipConfig used for this simulation run.

        Returns:
            A fully populated FeatureAnalysisContext including churn segment data
            when the ``about_to_churn`` column is present.
        """
        result_summary = self.to_summary_dict()
        kpi_metrics = self.get_kpi_metrics()
        result_summary.update(kpi_metrics)

        # Reuse get_segments() to avoid duplicating churn computation
        segments = self.get_segments()
        segment_data: dict[str, Any] | None = None
        if segments is not None:
            churn = segments.get("churn", {})
            non_churn = segments.get("non-churn", {})
            segment_data = {
                "churn_player_count": int(churn.get("Player Count", 0)),
                "churn_mean_points": churn.get("Avg Points / Player", 0.0),
                "churn_median_points": churn.get("Median Points / Player", 0.0),
                "churn_total_points": churn.get("Total Points", 0.0),
                "non_churn_player_count": int(non_churn.get("Player Count", 0)),
                "non_churn_mean_points": non_churn.get("Avg Points / Player", 0.0),
                "non_churn_median_points": non_churn.get("Median Points / Player", 0.0),
                "non_churn_total_points": non_churn.get("Total Points", 0.0),
            }
            result_summary["churn_segment"] = segment_data

        return FeatureAnalysisContext(
            feature_name="coin_flip",
            result_summary=result_summary,
            distribution=self.get_distribution(),
            config=config.to_dict(),
            kpi_metrics=kpi_metrics,
            segment_data=segment_data,
        )
