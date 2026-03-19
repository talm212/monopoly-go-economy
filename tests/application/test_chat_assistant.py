"""Tests for the ChatAssistant application service.

Validates that ChatAssistant correctly builds prompts with simulation context,
manages conversation history, delegates to the LLM client, and handles errors
gracefully. All tests use a mocked LLM client -- no real API calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.chat_assistant import SYSTEM_PROMPT, ChatAssistant, Message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> AsyncMock:
    """AsyncMock that satisfies the LLMClient protocol."""
    return AsyncMock()


@pytest.fixture
def assistant(mock_llm: AsyncMock) -> ChatAssistant:
    """ChatAssistant wired with a mocked LLM client."""
    return ChatAssistant(llm_client=mock_llm)


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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChatAssistant:
    """ChatAssistant returns LLM responses and handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_answer_returns_string(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """answer() returns the LLM's text response as a string."""
        mock_llm.complete.return_value = "The mean points per player is 125.5."

        result = await assistant.answer(
            question="What is the mean points per player?",
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert isinstance(result, str)
        assert result == "The mean points per player is 125.5."

    @pytest.mark.asyncio
    async def test_context_includes_config(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt sent to LLM includes serialized config values."""
        mock_llm.complete.return_value = "Answer."

        await assistant.answer(
            question="Tell me about the config.",
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
    async def test_context_includes_result_summary(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt sent to LLM includes result summary data."""
        mock_llm.complete.return_value = "Answer."

        await assistant.answer(
            question="How many interactions?",
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
    async def test_context_includes_distribution(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Prompt sent to LLM includes success distribution data."""
        mock_llm.complete.return_value = "Answer."

        await assistant.answer(
            question="What does the distribution look like?",
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "Distribution" in prompt_arg
        assert "20000" in prompt_arg

    @pytest.mark.asyncio
    async def test_conversation_history_passed_to_llm(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """Conversation history messages appear in the prompt."""
        mock_llm.complete.return_value = "Follow-up answer."
        history = [
            Message(role="user", content="What is the threshold?"),
            Message(role="assistant", content="The threshold is 100.0."),
        ]

        await assistant.answer(
            question="And how many players exceed it?",
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
            history=history,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        assert "What is the threshold?" in prompt_arg
        assert "The threshold is 100.0." in prompt_arg
        assert "And how many players exceed it?" in prompt_arg

    @pytest.mark.asyncio
    async def test_history_limited_to_max_turns(
        self,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """History is trimmed to max_history most recent turns."""
        mock_llm.complete.return_value = "Answer."
        assistant = ChatAssistant(llm_client=mock_llm, max_history=2)

        history = [
            Message(role="user", content="Old question 1"),
            Message(role="assistant", content="Old answer 1"),
            Message(role="user", content="Recent question"),
            Message(role="assistant", content="Recent answer"),
        ]

        await assistant.answer(
            question="New question",
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
            history=history,
        )

        prompt_arg = mock_llm.complete.call_args[0][0]
        # Only the 2 most recent messages should be included
        assert "Old question 1" not in prompt_arg
        assert "Old answer 1" not in prompt_arg
        assert "Recent question" in prompt_arg
        assert "Recent answer" in prompt_arg

    @pytest.mark.asyncio
    async def test_error_returns_helpful_message(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """LLM exception returns a user-friendly error message, never crashes."""
        mock_llm.complete.side_effect = RuntimeError("API timeout")

        result = await assistant.answer(
            question="This will fail",
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        assert isinstance(result, str)
        assert "sorry" in result.lower() or "couldn't" in result.lower()

    @pytest.mark.asyncio
    async def test_system_prompt_is_data_analyst(
        self,
        assistant: ChatAssistant,
        mock_llm: AsyncMock,
        sample_result_summary: dict[str, Any],
        sample_distribution: dict[str, int],
        sample_config: dict[str, Any],
        sample_kpi_metrics: dict[str, float],
    ) -> None:
        """System prompt establishes a data analyst persona for the economy team."""
        mock_llm.complete.return_value = "Answer."

        await assistant.answer(
            question="Any question",
            result_summary=sample_result_summary,
            distribution=sample_distribution,
            config=sample_config,
            kpi_metrics=sample_kpi_metrics,
        )

        system_arg = (
            mock_llm.complete.call_args[1].get("system") or mock_llm.complete.call_args[0][1]
        )
        assert "data analyst" in system_arg.lower()
        assert "Monopoly Go" in system_arg
        assert "cite" in system_arg.lower() or "numbers" in system_arg.lower()
        assert "don't have enough data" in system_arg or "I don't have" in system_arg
