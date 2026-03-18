"""LLM client abstraction with swappable provider adapters."""

from src.infrastructure.llm.client import LLMClient, get_llm_client

__all__ = ["LLMClient", "get_llm_client"]
