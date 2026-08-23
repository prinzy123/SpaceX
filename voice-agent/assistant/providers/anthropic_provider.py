"""Claude. Docs: https://docs.claude.com/en/api/messages"""

from __future__ import annotations

from typing import Any

from assistant.config import settings
from assistant.providers.base import LLMResponse, ToolCall, parse_arguments


class AnthropicProvider:
    name = "claude"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RuntimeError(
                "The anthropic package is missing. Run: pip install anthropic"
            ) from exc

        key = api_key or settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in your .env file, or set "
                "LLM_PROVIDER=echo to try the assistant without any API key."
            )
        self.client = Anthropic(api_key=key)
        self.model = model or settings.claude_model

    # Claude expects tools as {name, description, input_schema}
    @staticmethod
    def _tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            for tool in tools
        ]

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Neutral format -> Claude's content-block format.

        Claude wants tool results as `user` messages containing tool_result
        blocks, and consecutive results must be merged into a single message.
        """
        out: list[dict[str, Any]] = []

        for message in messages:
            role = message["role"]

            if role == "tool":
                block = {
                    "type": "tool_result",
                    "tool_use_id": message["tool_call_id"],
                    "content": str(message.get("content", "")),
                }
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
                continue

            if role == "assistant":
                blocks: list[dict[str, Any]] = []
                if message.get("content"):
                    blocks.append({"type": "text", "text": message["content"]})
                for call in message.get("tool_calls", []):
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": call.arguments,
                        }
                    )
                if blocks:
                    out.append({"role": "assistant", "content": blocks})
                continue

            out.append({"role": "user", "content": message["content"]})

        return out

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=settings.max_tokens,
            system=system,
            messages=self._messages(messages),
            tools=self._tools(tools) if tools else [],
        )

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=parse_arguments(block.input))
                )

        return LLMResponse(text="".join(text_parts).strip(), tool_calls=calls, raw=response)
