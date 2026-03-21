"""AWS Bedrock adapter for production LLM access.

Uses boto3 to invoke Bedrock models with IAM authentication (no API keys
needed). The boto3 client is synchronous; for true async, consider
migrating to aioboto3 in the future.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import boto3

from src.infrastructure.llm.constants import DEFAULT_MAX_TOKENS, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


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

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to Bedrock's invoke_model API.

        Args:
            prompt: The user message to send.
            system: Optional system prompt. Uses a default if not provided.

        Returns:
            The model's text response.

        Note:
            boto3 is synchronous. For true async, consider aioboto3.
        """
        logger.info("Calling Bedrock (model=%s)", self._model_id)
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
