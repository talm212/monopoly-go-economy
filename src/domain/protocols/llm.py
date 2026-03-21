"""LLM protocols — contract for language model client adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Contract for LLM client adapters.

    All adapters (Anthropic direct, Bedrock, etc.) implement this
    protocol to provide a uniform interface for text completion.
    """

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to the LLM and return the text response.

        Args:
            prompt: The user message to send.
            system: Optional system prompt. Defaults to a generic assistant prompt.

        Returns:
            The model's text response.
        """
        ...
