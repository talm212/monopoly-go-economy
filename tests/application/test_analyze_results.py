"""Tests for the InsightsAnalyst engine.

Validates that InsightsAnalyst correctly builds prompts, parses LLM responses,
and handles edge cases (malformed JSON, empty responses, errors) gracefully.
All tests use a mocked LLM client -- no real API calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.analyze_results import SYSTEM_PROMPT, InsightsAnalyst
from src.domain.models.insight import Insight, Severity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> AsyncMock:
    """AsyncMock that satisfies the LLMClient protocol."""
    return AsyncMock()


@pytest.fixture
def analyst(mock_llm: AsyncMock) -> InsightsAnalyst:
    """InsightsAnalyst wired with a mocked LLM client."""
    return InsightsAnalyst(llm_client=mock_llm)


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Coin flip config dict for prompt building."""
    return {
        "max_successes": 5,
        "probabilities": [0.60, 0.50, 0.50, 0.50, 0.50],
        "point_values": [1.0, 2.0, 4.0, 8.0, 16.0],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


@pytest.fixture
def sample_result_summary() -> dict[str, Any]:
    """Result summary dict for prompt building."""
    return {
        "total_interactions": 50000,
        "total_points": 125000.5,
        "players_above_threshold": 350,
        "threshold": 100.0,
    }


@pytest.fixture
def sample_distribution() -> dict[str, int]:
    """Success depth distribution for prompt building."""
    return {"0": 20000, "1": 12000, "2": 8000, "3": 5000, "4": 3000, "5": 2000}


@pytest.fixture
def sample_kpi_metrics() -> dict[str, float]:
    """KPI metrics for prompt building."""
    return {
        "mean_points_per_player": 125.5,
        "median_points_per_player": 95.2,
        "total_points": 125000.5,
        "pct_above_threshold": 0.35,
    }


VALID_LLM_RESPONSE = json.dumps([
    {
        "finding": "High churn boost impact",
        "severity": "warning",
        "recommendation": "Consider reducing churn boost to 1.15",
        "metric_references": {"churn_avg_points": 150.5, "non_churn_avg_points": 95.2},
    }
])

MULTI_INSIGHT_RESPONSE = json.dumps([
    {
        "finding": "High churn boost impact",
        "severity": "warning",
        "recommendation": "Consider reducing churn boost to 1.15",
        "metric_references": {"churn_avg_points": 150.5},
    },
    {
        "finding": "Distribution looks healthy",
        "severity": "info",
        "recommendation": "No changes needed",
        "metric_references": {"p50_depth": 2.0, "p90_depth": 4.0},
    },
    {
        "finding": "Threshold exceeded by too many players",
        "severity": "critical",
        "recommendation": "Raise threshold to 150",
        "metric_references": {"pct_above_threshold": 0.65},
    },
])


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInsightsAnalystHappyPath:
    """InsightsAnalyst returns correctly parsed insights from LLM responses."""

    @pytest.mark.asyncio
    async def test_generate_insights_returns_list_of_insights(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """LLM response is parsed into a list of Insight objects."""
        mock_llm.complete.return_value = VALID_LLM_RESPONSE

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
            feature_name="coin_flip",
        )

        assert len(insights) == 1
        assert isinstance(insights[0], Insight)
        assert insights[0].finding == "High churn boost impact"
        assert insights[0].severity == Severity.WARNING
        assert insights[0].recommendation == "Consider reducing churn boost to 1.15"
        assert insights[0].metric_references == {
            "churn_avg_points": 150.5,
            "non_churn_avg_points": 95.2,
        }

    @pytest.mark.asyncio
    async def test_multiple_insights_parsed(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Multiple insights in LLM response are all parsed."""
        mock_llm.complete.return_value = MULTI_INSIGHT_RESPONSE

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert len(insights) == 3
        severities = [i.severity for i in insights]
        assert Severity.WARNING in severities
        assert Severity.INFO in severities
        assert Severity.CRITICAL in severities

    @pytest.mark.asyncio
    async def test_default_feature_name_is_simulation(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Default feature_name is 'simulation' when not specified."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "simulation simulation results" in prompt_arg


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPromptConstruction:
    """Prompt sent to LLM contains config, results, distribution, and KPIs."""

    @pytest.mark.asyncio
    async def test_prompt_includes_config_data(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt includes serialized config values."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "max_successes" in prompt_arg
        assert "0.6" in prompt_arg
        assert "churn_boost_multiplier" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_includes_result_summary(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt includes result summary data."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "total_interactions" in prompt_arg
        assert "50000" in prompt_arg
        assert "players_above_threshold" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_includes_distribution(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt includes success distribution data."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "Success Distribution" in prompt_arg
        assert "20000" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_includes_kpi_metrics(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt includes KPI metrics."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "KPI Metrics" in prompt_arg
        assert "mean_points_per_player" in prompt_arg
        assert "125.5" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_includes_feature_name(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt includes the feature name for context."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
            feature_name="coin_flip",
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "coin_flip" in prompt_arg

    @pytest.mark.asyncio
    async def test_system_prompt_is_economy_focused(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """System prompt establishes economy analyst context."""
        mock_llm.complete.return_value = "[]"

        await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        system_arg = mock_llm.complete.call_args[1].get("system") or mock_llm.complete.call_args[0][1]
        assert "economy" in system_arg.lower()
        assert "Monopoly Go" in system_arg
        assert "JSON" in system_arg

    @pytest.mark.asyncio
    async def test_system_prompt_requests_json_array(self) -> None:
        """SYSTEM_PROMPT constant instructs JSON array output."""
        assert "JSON array" in SYSTEM_PROMPT
        assert "finding" in SYSTEM_PROMPT
        assert "severity" in SYSTEM_PROMPT
        assert "recommendation" in SYSTEM_PROMPT
        assert "metric_references" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestErrorHandling:
    """InsightsAnalyst handles malformed responses and errors gracefully."""

    @pytest.mark.asyncio
    async def test_handles_malformed_llm_response(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Malformed JSON from LLM returns empty list instead of crashing."""
        mock_llm.complete.return_value = "This is not JSON at all { broken ]"

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert insights == []

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Empty JSON array from LLM returns empty insights list."""
        mock_llm.complete.return_value = "[]"

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert insights == []

    @pytest.mark.asyncio
    async def test_llm_exception_returns_empty_list(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """LLM client exception is caught and returns empty list."""
        mock_llm.complete.side_effect = RuntimeError("API timeout")

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert insights == []

    @pytest.mark.asyncio
    async def test_response_not_a_list_returns_empty(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """LLM returns valid JSON but not a list -- returns empty."""
        mock_llm.complete.return_value = '{"finding": "single object, not array"}'

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert insights == []

    @pytest.mark.asyncio
    async def test_invalid_severity_skips_insight(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Insight with invalid severity is skipped, valid ones are kept."""
        response = json.dumps([
            {
                "finding": "Valid insight",
                "severity": "info",
                "recommendation": "All good",
                "metric_references": {"x": 1.0},
            },
            {
                "finding": "Bad severity",
                "severity": "catastrophic",
                "recommendation": "Panic",
                "metric_references": {"y": 2.0},
            },
        ])
        mock_llm.complete.return_value = response

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert len(insights) == 1
        assert insights[0].finding == "Valid insight"

    @pytest.mark.asyncio
    async def test_missing_field_skips_insight(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Insight missing a required field is skipped."""
        response = json.dumps([
            {
                "finding": "Missing recommendation",
                "severity": "info",
                # "recommendation" is missing
                "metric_references": {"x": 1.0},
            },
            {
                "finding": "Complete insight",
                "severity": "warning",
                "recommendation": "Do something",
                "metric_references": {"z": 3.0},
            },
        ])
        mock_llm.complete.return_value = response

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert len(insights) == 1
        assert insights[0].finding == "Complete insight"

    @pytest.mark.asyncio
    async def test_json_with_markdown_wrapper_is_handled(
        self,
        analyst: InsightsAnalyst,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """LLM wrapping JSON in markdown code fences is still parsed."""
        inner_json = json.dumps([
            {
                "finding": "Wrapped in markdown",
                "severity": "info",
                "recommendation": "No action needed",
                "metric_references": {"val": 42.0},
            }
        ])
        mock_llm.complete.return_value = f"```json\n{inner_json}\n```"

        insights = await analyst.generate_insights(
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert len(insights) == 1
        assert insights[0].finding == "Wrapped in markdown"
