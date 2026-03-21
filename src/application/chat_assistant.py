"""Chat assistant: natural language Q&A about simulation data.

Accepts a user question plus simulation context (config, results,
distribution, KPIs) and delegates to an LLM for a conversational answer.
Maintains conversation history with configurable turn limits to
prevent context overflow.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from src.domain.protocols import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a data analyst assistant for the Monopoly Go economy team.
You have access to simulation results and configuration data.

## How the Coin Flip Feature Works
Players land on a tile and trigger a coin-flip chain. Each flip is independent with
its own probability (p_success_1 through p_success_N). The chain stops on the first
tails. Points are cumulative: reaching depth 3 earns points_success_1 + points_success_2
+ points_success_3, multiplied by avg_multiplier.

## Config Parameters (what the user can edit in the dashboard)
**Flip Configuration tab:**
- p_success_1..N: Probability of heads at each flip depth (0-100%).
- points_success_1..N: Points awarded at each depth. Cumulative.
- max_successes: Maximum chain length.

**Simulation Settings tab:**
- reward_threshold: Point cutoff for the "% Above Threshold" KPI. Does NOT change
  gameplay — only how results are measured. User can adjust this to set reward tiers.
- churn_boost_multiplier: Multiplier on flip probabilities for about-to-churn players.
  E.g., 1.3 = 30% boost, capped at 100%.

## KPI Metrics (shown as cards at the top of the dashboard)
- mean_points_per_player: Average total_points across all players.
- median_points_per_player: Median total_points.
- total_points: Sum of all players' total_points.
- pct_above_threshold: Fraction of players with total_points > reward_threshold.

## Dashboard Tabs (what the user sees)
- **Charts**: Distribution of success depths + points histogram across players.
- **Churn Analysis**: Side-by-side comparison of churn vs non-churn player segments.
- **Data Table**: Full per-player results with CSV download.

## Rules
- Always cite specific numbers from the data when answering
- If you cannot answer from the provided data, say "I don't have enough data to answer that"
- Be concise and actionable
- Use plain language the economy team can understand
- When comparing metrics, show the actual values
- When suggesting config changes, tell the user WHERE to find the parameter
  (e.g., "Adjust reward_threshold in the Simulation Settings tab")"""


@dataclass
class Message:
    """A single conversation turn in the chat history.

    Attributes:
        role: Either "user" or "assistant".
        content: The message text.
    """

    role: Literal["user", "assistant"]
    content: str


class ChatAssistant:
    """Natural language Q&A about simulation data.

    Builds a prompt from simulation context and conversation history,
    delegates to the injected LLMClient, and returns the text response.
    All LLM errors are caught and logged -- never crashes the caller.
    """

    def __init__(self, llm_client: LLMClient, max_history: int = 10) -> None:
        self._llm = llm_client
        self._max_history = max_history

    async def answer(
        self,
        question: str,
        result_summary: dict[str, Any],
        distribution: dict[str, int],
        config: dict[str, Any],
        kpi_metrics: dict[str, float],
        history: list[Message] | None = None,
    ) -> str:
        """Answer a user question using simulation context and conversation history.

        Args:
            question: The user's natural language question.
            result_summary: High-level summary dict from SimulationResult.to_summary_dict().
            distribution: Success distribution from SimulationResult.get_distribution().
            config: Configuration dict from SimulatorConfig.to_dict().
            kpi_metrics: KPI dict from SimulationResult.get_kpi_metrics().
            history: Previous conversation turns. Trimmed to max_history most recent.

        Returns:
            The LLM's text response, or a user-friendly error message on failure.
        """
        context = self._build_context(result_summary, distribution, config, kpi_metrics)
        prompt = self._build_prompt(question, context, history)

        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
            return response
        except Exception as exc:
            logger.exception("Chat assistant failed to answer question")
            return (
                f"Failed to get a response from the LLM.\n\n"
                f"**Error:** `{type(exc).__name__}: {exc}`\n\n"
                f"Check that your LLM provider is configured correctly "
                f"(LLM_PROVIDER env var, AWS credentials for Bedrock, "
                f"or ANTHROPIC_API_KEY for Anthropic)."
            )

    def _build_context(
        self,
        result_summary: dict[str, Any],
        distribution: dict[str, int],
        config: dict[str, Any],
        kpi_metrics: dict[str, float],
    ) -> str:
        """Build the data context section of the prompt."""
        return (
            "Current simulation data:\n\n"
            f"Config: {json.dumps(config, indent=2)}\n\n"
            f"Result Summary: {json.dumps(result_summary, indent=2)}\n\n"
            f"Distribution: {json.dumps(distribution, indent=2)}\n\n"
            f"KPI Metrics: {json.dumps(kpi_metrics, indent=2)}"
        )

    def _build_prompt(
        self,
        question: str,
        context: str,
        history: list[Message] | None,
    ) -> str:
        """Build the full prompt with context, history, and the new question."""
        parts: list[str] = [context]

        if history:
            recent = history[-self._max_history :]
            for msg in recent:
                parts.append(f"{msg.role}: {msg.content}")

        parts.append(f"User question: {question}")
        return "\n\n".join(parts)
