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
from typing import Any

from src.infrastructure.llm.client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a data analyst assistant for the Monopoly Go economy team.
You have access to simulation results and configuration data.

Rules:
- Always cite specific numbers from the data when answering
- If you cannot answer from the provided data, say "I don't have enough data to answer that"
- Be concise and actionable
- Use plain language the economy team can understand
- When comparing metrics, show the actual values"""


@dataclass
class Message:
    """A single conversation turn in the chat history.

    Attributes:
        role: Either "user" or "assistant".
        content: The message text.
    """

    role: str
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
        except Exception:
            logger.exception("Chat assistant failed to answer question")
            return "Sorry, I couldn't process your question. Please try again."

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
