"""AWS Bedrock adapter for production LLM access.

Uses boto3 to invoke Bedrock models with IAM authentication (no API keys
needed). Supports both Anthropic models (invoke_model API) and non-Anthropic
models (converse API) via automatic detection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import boto3

from src.infrastructure.llm.constants import DEFAULT_MAX_TOKENS, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Top models available on Bedrock with math/stats benchmark scores
BEDROCK_MODELS: dict[str, str] = {
    "Claude Opus 4.6 (MATH 96.4%)": "us.anthropic.claude-opus-4-6",
    "Claude Sonnet 4.6 (MATH 94%)": "us.anthropic.claude-sonnet-4-6",
    "DeepSeek R1 (MATH 90%)": "us.deepseek.r1-v1:0",
    "Meta Llama 4 Maverick (MATH 85%)": "us.meta.llama4-maverick-17b-instruct-v1:0",
    "Amazon Nova Pro (MATH 80%)": "us.amazon.nova-pro-v1:0",
}

DEFAULT_MODEL_LABEL = "Claude Sonnet 4.6 (MATH 94%)"


class BedrockAdapter:
    """AWS Bedrock adapter for production. Uses IAM auth (no API keys)."""

    def __init__(
        self,
        region: str | None = None,
        model_id: str = "us.anthropic.claude-sonnet-4-6",
    ) -> None:
        resolved_region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-runtime", region_name=resolved_region)
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        """Return the current model ID."""
        return self._model_id

    @model_id.setter
    def model_id(self, value: str) -> None:
        """Update the model ID."""
        self._model_id = value

    def _is_anthropic_model(self) -> bool:
        """Check if the current model is an Anthropic model."""
        return "anthropic" in self._model_id

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to Bedrock.

        Automatically uses the correct API:
        - invoke_model with Anthropic message format for Claude models
        - converse API for all other models (DeepSeek, Llama, Nova, etc.)
        """
        if self._is_anthropic_model():
            return await self._complete_anthropic(prompt, system)
        return await self._complete_converse(prompt, system)

    async def _complete_anthropic(self, prompt: str, system: str) -> str:
        """Invoke an Anthropic model using the Messages API format."""
        logger.info("Calling Bedrock Anthropic (model=%s)", self._model_id)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": DEFAULT_MAX_TOKENS,
            "system": system if system else DEFAULT_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = await asyncio.to_thread(
            self._client.invoke_model,
            modelId=self._model_id,
            body=json.dumps(body),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        content = result.get("content", [])
        text_blocks = [b for b in content if isinstance(b, dict) and "text" in b]
        if not text_blocks:
            raise ValueError("LLM returned no text content")
        return text_blocks[0]["text"]

    async def _complete_converse(self, prompt: str, system: str) -> str:
        """Invoke a non-Anthropic model using the Bedrock Converse API."""
        logger.info("Calling Bedrock Converse (model=%s)", self._model_id)
        system_messages = []
        if system:
            system_messages = [{"text": system}]

        messages = [
            {"role": "user", "content": [{"text": prompt}]},
        ]

        response = await asyncio.to_thread(
            self._client.converse,
            modelId=self._model_id,
            messages=messages,
            system=system_messages,
            inferenceConfig={"maxTokens": 4096},
        )
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        text_blocks = [b["text"] for b in content if "text" in b]
        if not text_blocks:
            raise ValueError("LLM returned no text content")
        return text_blocks[0]
