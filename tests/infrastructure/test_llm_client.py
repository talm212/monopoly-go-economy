"""Tests for LLM client abstraction and provider adapters.

Verifies that:
- LLMClient protocol is @runtime_checkable
- AnthropicAdapter implements LLMClient and calls the Anthropic API correctly
- BedrockAdapter implements LLMClient and calls the Bedrock API correctly
- get_llm_client() factory returns the correct adapter based on LLM_PROVIDER env var
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from src.infrastructure.llm.bedrock_adapter import BedrockAdapter
from src.domain.protocols import LLMClient
from src.infrastructure.llm.client import get_llm_client

# ---------------------------------------------------------------------------
# Protocol conformance tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMClientProtocol:
    """Verify LLMClient protocol is @runtime_checkable and adapters conform."""

    def test_anthropic_adapter_implements_protocol(self) -> None:
        with patch("src.infrastructure.llm.anthropic_adapter.AsyncAnthropic"):
            adapter = AnthropicAdapter(api_key="test-key")
        assert isinstance(adapter, LLMClient)

    def test_bedrock_adapter_implements_protocol(self) -> None:
        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            adapter = BedrockAdapter()
        assert isinstance(adapter, LLMClient)


# ---------------------------------------------------------------------------
# AnthropicAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnthropicAdapter:
    """Verify AnthropicAdapter correctly wraps the Anthropic async client."""

    @pytest.mark.asyncio
    async def test_complete_calls_api(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]
        mock_client.messages.create.return_value = mock_response

        with patch(
            "src.infrastructure.llm.anthropic_adapter.AsyncAnthropic",
            return_value=mock_client,
        ):
            adapter = AnthropicAdapter(api_key="test-key")

        result = await adapter.complete("Say hello")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"] == [{"role": "user", "content": "Say hello"}]
        assert result == "Hello from Claude"

    @pytest.mark.asyncio
    async def test_complete_returns_string(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="test response")]
        mock_client.messages.create.return_value = mock_response

        with patch(
            "src.infrastructure.llm.anthropic_adapter.AsyncAnthropic",
            return_value=mock_client,
        ):
            adapter = AnthropicAdapter(api_key="test-key")

        result = await adapter.complete("test prompt")
        assert isinstance(result, str)
        assert result == "test response"

    @pytest.mark.asyncio
    async def test_complete_passes_system_prompt(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_response

        with patch(
            "src.infrastructure.llm.anthropic_adapter.AsyncAnthropic",
            return_value=mock_client,
        ):
            adapter = AnthropicAdapter(api_key="test-key")

        await adapter.complete("prompt", system="You are a game designer.")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are a game designer."

    @pytest.mark.asyncio
    async def test_complete_uses_default_system_prompt(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_response

        with patch(
            "src.infrastructure.llm.anthropic_adapter.AsyncAnthropic",
            return_value=mock_client,
        ):
            adapter = AnthropicAdapter(api_key="test-key")

        await adapter.complete("prompt")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_complete_passes_model_and_max_tokens(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_response

        with patch(
            "src.infrastructure.llm.anthropic_adapter.AsyncAnthropic",
            return_value=mock_client,
        ):
            adapter = AnthropicAdapter(api_key="test-key", model="claude-sonnet-4-20250514")

        await adapter.complete("prompt")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 4096


# ---------------------------------------------------------------------------
# BedrockAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBedrockAdapter:
    """Verify BedrockAdapter correctly wraps the Bedrock boto3 client."""

    @pytest.mark.asyncio
    async def test_complete_calls_bedrock(self) -> None:
        mock_bedrock_client = MagicMock()
        response_body = json.dumps(
            {
                "content": [{"text": "Hello from Bedrock"}],
            }
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter()

        result = await adapter.complete("Say hello")

        mock_bedrock_client.invoke_model.assert_called_once()
        call_kwargs = mock_bedrock_client.invoke_model.call_args.kwargs
        body = json.loads(call_kwargs["body"])
        assert body["messages"] == [{"role": "user", "content": "Say hello"}]
        assert result == "Hello from Bedrock"

    @pytest.mark.asyncio
    async def test_complete_returns_string(self) -> None:
        mock_bedrock_client = MagicMock()
        response_body = json.dumps(
            {
                "content": [{"text": "test response"}],
            }
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter()

        result = await adapter.complete("test prompt")
        assert isinstance(result, str)
        assert result == "test response"

    @pytest.mark.asyncio
    async def test_complete_passes_system_prompt(self) -> None:
        mock_bedrock_client = MagicMock()
        response_body = json.dumps(
            {
                "content": [{"text": "response"}],
            }
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter()

        await adapter.complete("prompt", system="You are a game designer.")

        call_kwargs = mock_bedrock_client.invoke_model.call_args.kwargs
        body = json.loads(call_kwargs["body"])
        assert body["system"] == "You are a game designer."

    @pytest.mark.asyncio
    async def test_complete_sends_correct_model_id(self) -> None:
        mock_bedrock_client = MagicMock()
        response_body = json.dumps(
            {
                "content": [{"text": "response"}],
            }
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter(
                model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            )

        await adapter.complete("prompt")

        call_kwargs = mock_bedrock_client.invoke_model.call_args.kwargs
        assert call_kwargs["modelId"] == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert call_kwargs["contentType"] == "application/json"


# ---------------------------------------------------------------------------
# BedrockAdapter extended tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBedrockAdapterExtended:
    """Additional coverage for BedrockAdapter: model_id mutation, converse
    response format, and parametrized model ID tests."""

    @pytest.mark.asyncio
    async def test_model_id_setter(self) -> None:
        """Create adapter, change model_id, verify the new ID is used."""
        mock_bedrock_client = MagicMock()
        response_body = json.dumps(
            {"content": [{"text": "response"}]}
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter(model_id="us.anthropic.claude-sonnet-4-6")

        # Mutate model_id
        adapter._model_id = "us.amazon.nova-pro-v1:0"

        await adapter.complete("test")

        call_kwargs = mock_bedrock_client.invoke_model.call_args.kwargs
        assert call_kwargs["modelId"] == "us.amazon.nova-pro-v1:0"

    @pytest.mark.asyncio
    async def test_complete_with_converse_style_response(self) -> None:
        """Test handling of a Converse-API-style response body with content blocks."""
        mock_bedrock_client = MagicMock()
        # Converse API returns content as a list of typed blocks
        converse_response = json.dumps(
            {
                "content": [
                    {"type": "text", "text": "Analysis: the distribution looks balanced."},
                ],
            }
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = converse_response
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter()

        result = await adapter.complete("Analyze the data")
        assert result == "Analysis: the distribution looks balanced."

    @pytest.mark.asyncio
    async def test_complete_raises_on_empty_content(self) -> None:
        """Empty content array should raise ValueError."""
        mock_bedrock_client = MagicMock()
        response_body = json.dumps({"content": []}).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter()

        with pytest.raises(ValueError, match="no text content"):
            await adapter.complete("test")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "model_id",
        [
            "us.anthropic.claude-sonnet-4-6",
            "anthropic.claude-sonnet-4-20250514-v1:0",
            "us.amazon.nova-pro-v1:0",
            "meta.llama3-70b-instruct-v1:0",
        ],
    )
    async def test_parametrized_model_ids(self, model_id: str) -> None:
        """Verify completion works with various model IDs (anthropic and non-anthropic)."""
        mock_bedrock_client = MagicMock()
        response_body = json.dumps(
            {"content": [{"text": f"Response from {model_id}"}]}
        ).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = response_body
        mock_bedrock_client.invoke_model.return_value = {"body": mock_body}

        with patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_bedrock_client
            adapter = BedrockAdapter(model_id=model_id)

        result = await adapter.complete("hello")

        assert result == f"Response from {model_id}"
        call_kwargs = mock_bedrock_client.invoke_model.call_args.kwargs
        assert call_kwargs["modelId"] == model_id

    def test_is_anthropic_model_detection(self) -> None:
        """Verify model ID string detection for anthropic vs non-anthropic models."""
        anthropic_ids = [
            "us.anthropic.claude-sonnet-4-6",
            "anthropic.claude-sonnet-4-20250514-v1:0",
        ]
        non_anthropic_ids = [
            "us.amazon.nova-pro-v1:0",
            "meta.llama3-70b-instruct-v1:0",
        ]

        for mid in anthropic_ids:
            assert "anthropic" in mid, f"Expected 'anthropic' in {mid}"

        for mid in non_anthropic_ids:
            assert "anthropic" not in mid, f"Did not expect 'anthropic' in {mid}"


# ---------------------------------------------------------------------------
# Factory function tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetLlmClient:
    """Verify get_llm_client() factory dispatches based on LLM_PROVIDER env var."""

    def test_default_returns_bedrock(self) -> None:
        """Default provider (no LLM_PROVIDER set) returns BedrockAdapter."""
        import os

        env = os.environ.copy()
        env.pop("LLM_PROVIDER", None)
        with patch.dict("os.environ", env, clear=True):
            client = get_llm_client()
        assert isinstance(client, BedrockAdapter)

    def test_anthropic_provider_returns_anthropic(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
                clear=False,
            ),
            patch(
                "src.infrastructure.llm.anthropic_adapter.AsyncAnthropic",
            ),
        ):
            client = get_llm_client()
        assert isinstance(client, AnthropicAdapter)

    def test_bedrock_provider_returns_bedrock(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"LLM_PROVIDER": "bedrock"},
                clear=False,
            ),
            patch("src.infrastructure.llm.bedrock_adapter.boto3") as mock_boto3,
        ):
            mock_boto3.client.return_value = MagicMock()
            client = get_llm_client()
        assert isinstance(client, BedrockAdapter)

    def test_unknown_provider_raises(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"LLM_PROVIDER": "openai"},
                clear=False,
            ),
            pytest.raises(ValueError, match="Unknown LLM provider: openai"),
        ):
            get_llm_client()
