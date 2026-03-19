"""Insights analyst engine: AI-powered analysis of simulation results.

Takes simulation output (as plain dicts) and uses an LLM to generate
actionable insights for the economy team. Feature-agnostic -- works with
any simulator that produces summary dicts, distributions, and KPI metrics.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.domain.models.insight import Insight, Severity
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.llm.utils import strip_markdown_fences

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior economy analyst for the Monopoly Go game.
Analyze simulation results and provide insights as a JSON array.

Each insight must have:
- "finding": What you observed (be specific with numbers)
- "severity": "info", "warning", or "critical"
- "recommendation": Actionable suggestion for the economy team
- "metric_references": Dict of metric_name: value that support your finding

Focus on:
1. Distribution anomalies (too many/few players at extreme success depths)
2. Churn boost effectiveness (is it too generous or too weak?)
3. Points economy balance (are total points within expected range?)
4. Threshold analysis (what % of players exceed the reward threshold?)
5. Risk areas (could this config be exploited or cause inflation?)

Return ONLY a valid JSON array of insights. No markdown, no explanation."""

_SEVERITY_MAP: dict[str, Severity] = {s.value: s for s in Severity}


class InsightsAnalyst:
    """Analyzes simulation results and generates actionable insights via LLM.

    Accepts plain dicts (not protocol objects) to stay generic and testable.
    All LLM errors are caught and logged -- never crashes the caller.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def generate_insights(
        self,
        result_summary: dict[str, Any],
        distribution: dict[str, int],
        config: dict[str, Any],
        kpi_metrics: dict[str, float],
        feature_name: str = "simulation",
    ) -> list[Insight]:
        """Generate AI-powered insights from simulation results.

        Args:
            result_summary: High-level summary dict from SimulationResult.to_summary_dict().
            distribution: Success distribution from SimulationResult.get_distribution().
            config: Configuration dict from SimulatorConfig.to_dict().
            kpi_metrics: KPI dict from SimulationResult.get_kpi_metrics().
            feature_name: Name of the simulation feature for prompt context.

        Returns:
            List of Insight objects. Empty list on any error.
        """
        prompt = self._build_prompt(result_summary, distribution, config, kpi_metrics, feature_name)

        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
            return self._parse_insights(response)
        except Exception:
            logger.exception("Failed to generate insights")
            return []

    def _build_prompt(
        self,
        result_summary: dict[str, Any],
        distribution: dict[str, int],
        config: dict[str, Any],
        kpi_metrics: dict[str, float],
        feature_name: str,
    ) -> str:
        """Build the user prompt with all simulation data."""
        return (
            f"Analyze these {feature_name} simulation results:\n\n"
            f"**Configuration:**\n{json.dumps(config, indent=2)}\n\n"
            f"**Result Summary:**\n{json.dumps(result_summary, indent=2)}\n\n"
            f"**Success Distribution:**\n{json.dumps(distribution, indent=2)}\n\n"
            f"**KPI Metrics:**\n{json.dumps(kpi_metrics, indent=2)}\n\n"
            "Provide 3-5 actionable insights as a JSON array."
        )

    def _parse_insights(self, response: str) -> list[Insight]:
        """Parse the LLM JSON response into Insight objects.

        Gracefully handles malformed JSON, markdown-wrapped JSON,
        invalid severity values, and missing fields by skipping
        problematic entries.
        """
        cleaned = strip_markdown_fences(response)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response; returning empty insights")
            return []

        if not isinstance(parsed, list):
            logger.warning("LLM response is not a JSON array; returning empty insights")
            return []

        insights: list[Insight] = []
        for item in parsed:
            insight = self._parse_single_insight(item)
            if insight is not None:
                insights.append(insight)

        return insights

    def _parse_single_insight(self, item: Any) -> Insight | None:
        """Parse a single dict into an Insight, returning None on failure."""
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict insight item: %s", type(item).__name__)
            return None

        try:
            finding = item["finding"]
            severity_str = item["severity"]
            recommendation = item["recommendation"]
            metric_references = item["metric_references"]
        except KeyError as exc:
            logger.warning("Skipping insight with missing field: %s", exc)
            return None

        severity = _SEVERITY_MAP.get(severity_str)
        if severity is None:
            logger.warning("Skipping insight with invalid severity: %s", severity_str)
            return None

        try:
            refs = {str(k): float(v) for k, v in metric_references.items()}
        except (ValueError, TypeError):
            refs = {}

        return Insight(
            finding=str(finding),
            severity=severity,
            recommendation=str(recommendation),
            metric_references=refs,
        )
