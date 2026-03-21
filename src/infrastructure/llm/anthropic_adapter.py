"""Anthropic API adapter for direct LLM access during local development.

Uses the official anthropic Python package with AsyncAnthropic for
non-blocking calls. Requires an ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from src.infrastructure.llm.constants import DEFAULT_MAX_TOKENS, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AnthropicAdapter:
    """Direct Anthropic API adapter for local development."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set. " "Export it or use LLM_PROVIDER=bedrock."
            )
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to the Anthropic Messages API.

        Args:
            prompt: The user message to send.
            system: Optional system prompt. Uses a default if not provided.

        Returns:
            The model's text response.
        """
        logger.info("Calling Anthropic API (model=%s)", self._model)
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system if system else DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b for b in response.content if hasattr(b, "text")]
        if not text_blocks:
            raise ValueError("LLM returned no text content")
        return text_blocks[0].text
