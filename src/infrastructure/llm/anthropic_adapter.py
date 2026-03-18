"""Anthropic API adapter for direct LLM access during local development.

Uses the official anthropic Python package with AsyncAnthropic for
non-blocking calls. Requires an ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


class AnthropicAdapter:
    """Direct Anthropic API adapter for local development."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
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
            max_tokens=4096,
            system=system if system else _DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
