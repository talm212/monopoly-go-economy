"""Insight domain model: structured output from AI-powered simulation analysis.

An Insight captures a specific finding about simulation results,
its severity, a recommendation for the economy team, and the
supporting metric references.  Optionally includes a parameter sweep
suggestion so the user can immediately explore the recommended range.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Severity level for an analysis insight."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SweepSuggestion:
    """A suggested parameter sweep to explore based on an insight.

    Attributes:
        parameter: Display name of the parameter (e.g. "reward_threshold").
        start: Start value for the sweep range.
        end: End value for the sweep range.
        steps: Number of sweep steps.
        reason: Brief explanation of why this sweep is recommended.
    """

    parameter: str
    start: float
    end: float
    steps: int = 5
    reason: str = ""


@dataclass(frozen=True)
class Insight:
    """A single actionable insight from simulation analysis.

    Attributes:
        finding: What was observed in the simulation results.
        severity: Severity level (info, warning, critical).
        recommendation: Actionable suggestion for the economy team.
        metric_references: Supporting data points as metric_name -> value.
        sweep_suggestion: Optional parameter sweep to explore the recommendation.
    """

    finding: str
    severity: Severity
    recommendation: str
    metric_references: dict[str, float]
    sweep_suggestion: SweepSuggestion | None = field(default=None)
