"""Patch langchain_aws ChatBedrock streaming to capture Anthropic Messages usage.

Bedrock Anthropic Messages streams report usage on ``message_start`` (input) and
``message_delta`` (output). langchain_aws ignores those fields and only reads
``amazon-bedrock-invocationMetrics`` on ``message_stop``.

Claude Sonnet 5 often omits invocation metrics, so streamed responses have no
``usage_metadata`` and CloudWatch token metrics never publish.

This patch attaches Anthropic usage onto the corresponding ``AIMessageChunk``s so
chunk aggregation sums tokens correctly.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PATCHED = False


def _usage_from_anthropic_event(stream_response: dict[str, Any]) -> dict[str, Any] | None:
    msg_type = stream_response.get("type")
    if msg_type == "message_start":
        usage = (stream_response.get("message") or {}).get("usage") or {}
        if not usage:
            return None
        cache_read = int(usage.get("cache_read_input_tokens") or 0)
        cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
        input_tokens = int(usage.get("input_tokens") or 0) + cache_read + cache_creation
        output_tokens = int(usage.get("output_tokens") or 0)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_token_details": {
                "cache_read": cache_read,
                "cache_creation": cache_creation,
            },
        }

    if msg_type == "message_delta":
        usage = stream_response.get("usage") or {}
        if not usage:
            return None
        output_tokens = int(usage.get("output_tokens") or 0)
        return {
            "input_tokens": 0,
            "output_tokens": output_tokens,
            "total_tokens": output_tokens,
        }

    return None


def apply_bedrock_stream_usage_patch() -> bool:
    """Monkey-patch langchain_aws stream chunk conversion. Idempotent."""
    global _PATCHED
    if _PATCHED:
        return True

    try:
        from langchain_aws.llms import bedrock as bedrock_llm
        from langchain_core.messages import AIMessageChunk
    except Exception as exc:
        logger.warning("Bedrock stream usage patch skipped (import failed): %s", exc)
        return False

    original = bedrock_llm._stream_response_to_generation_chunk

    def patched(
        stream_response: dict[str, Any],
        provider: str,
        output_key: str,
        messages_api: bool,
        coerce_content_to_string: bool,
    ):
        chunk = original(
            stream_response,
            provider=provider,
            output_key=output_key,
            messages_api=messages_api,
            coerce_content_to_string=coerce_content_to_string,
        )
        if not messages_api:
            return chunk

        usage_metadata = _usage_from_anthropic_event(stream_response)
        if not usage_metadata:
            return chunk

        if chunk is None:
            return AIMessageChunk(content="", usage_metadata=usage_metadata)

        if isinstance(chunk, AIMessageChunk):
            chunk.usage_metadata = usage_metadata
        return chunk

    bedrock_llm._stream_response_to_generation_chunk = patched
    _PATCHED = True
    logger.info("Applied ChatBedrock Anthropic stream usage_metadata patch")
    return True
