"""Insight domain model: structured output from AI-powered simulation analysis.

An Insight captures a specific finding about simulation results,
its severity, a recommendation for the economy team, and the
supporting metric references.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    """Severity level for an analysis insight."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Insight:
    """A single actionable insight from simulation analysis.

    Attributes:
        finding: What was observed in the simulation results.
        severity: Severity level (info, warning, critical).
        recommendation: Actionable suggestion for the economy team.
        metric_references: Supporting data points as metric_name -> value.
    """

    finding: str
    severity: Severity
    recommendation: str
    metric_references: dict[str, float]
