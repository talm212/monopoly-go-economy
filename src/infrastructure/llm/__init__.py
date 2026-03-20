"""LLM client abstraction with swappable provider adapters."""

from src.domain.protocols import LLMClient
from src.infrastructure.llm.client import get_llm_client

__all__ = ["LLMClient", "get_llm_client"]
