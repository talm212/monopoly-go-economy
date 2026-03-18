"""Optimization domain models: targets, directions, and iteration steps.

Defines the data structures used by the ConfigOptimizer to track
optimization goals, convergence criteria, and iteration history.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OptimizationDirection(Enum):
    """Direction for optimization: maximize, minimize, or hit a target value."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    TARGET = "target"


@dataclass(frozen=True)
class OptimizationTarget:
    """Immutable specification of what the optimizer should aim for.

    Attributes:
        metric: Name of the metric to optimize (e.g. "players_above_threshold").
        target_value: The desired value for the metric.
        direction: Whether to maximize, minimize, or target the value.
        tolerance: Fractional tolerance for convergence (0.05 = 5%).
    """

    metric: str
    target_value: float
    direction: OptimizationDirection
    tolerance: float = 0.05


@dataclass
class OptimizationStep:
    """Record of a single optimizer iteration.

    Attributes:
        iteration: 1-based iteration number.
        config: The config dict used for this iteration's simulation.
        result_metric: The observed value of the target metric.
        distance_to_target: Absolute distance from the target value.
    """

    iteration: int
    config: dict[str, Any]
    result_metric: float
    distance_to_target: float
