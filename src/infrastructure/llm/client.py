"""LLM client factory for provider-agnostic AI integration.

The LLMClient protocol lives in ``src.domain.protocols`` (Clean Architecture:
domain layer owns the contract). This module re-exports LLMClient for
backwards compatibility and provides the factory function that selects the
appropriate adapter based on the LLM_PROVIDER environment variable.
"""

from __future__ import annotations

import logging
import os

from src.domain.protocols import LLMClient

logger = logging.getLogger(__name__)

# Re-export so existing ``from src.infrastructure.llm.client import LLMClient``
# continues to work during the migration period.
__all__ = ["LLMClient", "get_llm_client"]


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
