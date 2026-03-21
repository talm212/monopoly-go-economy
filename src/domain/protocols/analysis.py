"""Analysis protocols — feature-agnostic context for AI analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FeatureAnalysisContext:
    """Generic AI analysis context that any feature simulator can produce.

    Encapsulates all the data needed by InsightsAnalyst, ChatAssistant,
    and ConfigOptimizer so the AI layer is feature-agnostic.

    Attributes:
        feature_name: Identifier for the simulation feature (e.g. "coin_flip").
        result_summary: High-level summary from SimulationResult.to_summary_dict().
        distribution: Outcome distribution from SimulationResult.get_distribution().
        config: Configuration dict from SimulatorConfig.to_dict().
        kpi_metrics: Key performance indicators from SimulationResult.get_kpi_metrics().
        segment_data: Optional breakdown by player segment (e.g. churn vs non-churn).
    """

    feature_name: str
    result_summary: dict[str, Any]
    distribution: dict[str, int]
    config: dict[str, Any]
    kpi_metrics: dict[str, float]
    segment_data: dict[str, Any] | None = field(default=None)
