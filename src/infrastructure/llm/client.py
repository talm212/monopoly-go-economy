"""LLM client protocol and factory for provider-agnostic AI integration.

Defines the LLMClient protocol that all LLM adapters must implement,
and a factory function that selects the appropriate adapter based on
the LLM_PROVIDER environment variable.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


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


def get_llm_client() -> LLMClient:
    """Factory that returns an LLM client based on the LLM_PROVIDER env var.

    Reads LLM_PROVIDER from the environment. Defaults to 'anthropic'.

    Returns:
        An LLMClient implementation for the configured provider.

    Raises:
        ValueError: If LLM_PROVIDER is set to an unknown value.
    """
    provider = os.environ.get("LLM_PROVIDER", "bedrock")
    logger.info("Creating LLM client for provider=%s", provider)

    if provider == "bedrock":
        from src.infrastructure.llm.bedrock_adapter import BedrockAdapter

        return BedrockAdapter()
    elif provider == "anthropic":
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        return AnthropicAdapter(api_key=api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
