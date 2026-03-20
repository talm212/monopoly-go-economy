"""AWS Bedrock adapter for production LLM access.

Uses boto3 to invoke Bedrock models with IAM authentication (no API keys
needed). The boto3 client is synchronous; for true async, consider
migrating to aioboto3 in the future.
"""

from __future__ import annotations

import asyncio
import json
import logging

import boto3

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


class BedrockAdapter:
    """AWS Bedrock adapter for production. Uses IAM auth (no API keys)."""

    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
    ) -> None:
        self._client = boto3.client("bedrock-runtime", region_name=region)
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
            "max_tokens": 4096,
            "system": system if system else _DEFAULT_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = await asyncio.to_thread(
            self._client.invoke_model,
            modelId=self._model_id,
            body=json.dumps(body),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
