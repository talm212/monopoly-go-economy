"""Provider-agnostic LLM model registry."""
from __future__ import annotations

AVAILABLE_MODELS: dict[str, str] = {
    "Claude Opus 4.6 (MATH 96.4%)": "us.anthropic.claude-opus-4-6",
    "Claude Sonnet 4.6 (MATH 94%)": "us.anthropic.claude-sonnet-4-6",
    "DeepSeek R1 (MATH 90%)": "us.deepseek.r1-v1:0",
    "Meta Llama 4 Maverick (MATH 85%)": "us.meta.llama4-maverick-17b-instruct-v1:0",
    "Amazon Nova Pro (MATH 80%)": "us.amazon.nova-pro-v1:0",
}

DEFAULT_MODEL_LABEL = "Claude Sonnet 4.6 (MATH 94%)"
