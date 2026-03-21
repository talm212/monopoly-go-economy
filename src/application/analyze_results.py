"""Insights analyst engine: AI-powered analysis of simulation results.

Takes simulation output (as plain dicts) and uses an LLM to generate
actionable insights for the economy team. Feature-agnostic -- works with
any simulator that produces summary dicts, distributions, and KPI metrics.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.application.llm_utils import strip_markdown_fences
from src.domain.models.insight import Insight, Severity, SweepSuggestion
from src.domain.protocols import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior economy analyst for the Monopoly Go game.
Analyze simulation results and provide insights as a JSON array.

## How the Coin Flip Feature Works
Players land on a tile and trigger a coin-flip chain. Each flip is independent with
its own probability (p_success_1 through p_success_N). The chain stops on the first
tails. Points are cumulative: reaching depth 3 earns points_success_1 + points_success_2
+ points_success_3, multiplied by avg_multiplier.

## Config Parameters (what the user can edit)
**Flip Configuration tab:**
- p_success_1..N: Probability of heads at each flip depth (0-100%). Higher = more players advance.
- points_success_1..N: Points awarded at each depth. Cumulative — depth 3 = sum of depths 1+2+3.
- max_successes: Maximum chain length. Determines how many flips a player can attempt.

**Simulation Settings tab:**
- reward_threshold: Point cutoff for the "% Above Threshold" KPI. Players above this
  value are counted. Does NOT change gameplay — only affects how results are reported.
  The user can edit this to set a meaningful reward tier.
- churn_boost_multiplier: Multiplier on flip probabilities for about-to-churn players
  (from CSV column about_to_churn). E.g., 1.3 = 30% boost, capped at 100%.
  Higher values give churn-risk players better odds to keep them engaged.

## KPI Metrics (what the user sees on the dashboard)
- mean_points_per_player: Average total_points across all players.
- median_points_per_player: Median total_points (shows distribution skew vs mean).
- total_points: Sum of all players' total_points (economy-wide inflation indicator).
- pct_above_threshold: Fraction of players whose total_points > reward_threshold.

## Parameter Sweep (available in the dashboard)
The user has a Parameter Sweep tool that can sweep any config parameter across a
range of values and chart KPI impact. Sweepable parameters include:
- p_success_1..N (probability at each depth, range 0.0–1.0)
- points_success_1..N (points at each depth)
- reward_threshold (KPI reporting cutoff)

## What to Analyze
Each insight must have:
- "finding": What you observed (be specific with numbers)
- "severity": "info", "warning", or "critical"
- "recommendation": Actionable suggestion for the economy team
- "metric_references": Dict of metric_name: value that support your finding
- "sweep_suggestion": (OPTIONAL, include only when a sweep would help) Object with:
  - "parameter": the parameter display name (e.g. "p_success_1", "reward_threshold")
  - "start": sweep start value (number)
  - "end": sweep end value (number)
  - "steps": number of steps (default 5)
  - "reason": brief explanation of why this sweep is useful

Only include sweep_suggestion when exploring a range would genuinely help the user
make a decision. Not every insight needs one — skip it for purely informational findings.

Focus on:
1. Distribution anomalies (too many/few players at extreme success depths)
2. Churn boost effectiveness (is it too generous or too weak?)
3. Points economy balance (are total points within expected range?)
4. Threshold analysis (is reward_threshold set meaningfully? If nearly all players exceed it, recommend raising it)
5. Risk areas (could this config be exploited or cause inflation?)

When referencing parameters, tell the user WHERE to find them in the UI
(e.g., "Adjust reward_threshold in the Simulation Settings tab").

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
            "Provide 3-5 actionable insights as a JSON array.\n"
            "IMPORTANT: At least 2 insights MUST include a sweep_suggestion so the user "
            "can immediately explore the parameter space. Choose the most impactful parameters."
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

        # Parse optional sweep suggestion
        sweep: SweepSuggestion | None = None
        sweep_raw = item.get("sweep_suggestion")
        if isinstance(sweep_raw, dict):
            try:
                sweep = SweepSuggestion(
                    parameter=str(sweep_raw["parameter"]),
                    start=float(sweep_raw["start"]),
                    end=float(sweep_raw["end"]),
                    steps=int(sweep_raw.get("steps", 5)),
                    reason=str(sweep_raw.get("reason", "")),
                )
            except (KeyError, ValueError, TypeError):
                logger.warning("Skipping malformed sweep_suggestion")

        return Insight(
            finding=str(finding),
            severity=severity,
            recommendation=str(recommendation),
            metric_references=refs,
            sweep_suggestion=sweep,
        )
