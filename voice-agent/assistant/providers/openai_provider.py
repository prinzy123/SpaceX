"""ChatGPT / GPT models. Docs: https://platform.openai.com/docs/guides/function-calling"""

from __future__ import annotations

from typing import Any

from assistant.config import settings
from assistant.providers.base import LLMResponse, ToolCall, parse_arguments


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RuntimeError("The openai package is missing. Run: pip install openai") from exc

        key = api_key or settings.openai_api_key
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Put it in your .env file, or set "
                "LLM_PROVIDER=echo to try the assistant without any API key."
            )
        self.client = OpenAI(api_key=key)
        self.model = model or settings.openai_model

    @staticmethod
    def _tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for tool in tools
        ]

    @staticmethod
    def _messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        import json

        out: list[dict[str, Any]] = [{"role": "system", "content": system}]

        for message in messages:
            role = message["role"]

            if role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": message["tool_call_id"],
                        "content": str(message.get("content", "")),
                    }
                )
                continue

            if role == "assistant":
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": message.get("content") or None,
                }
                if message.get("tool_calls"):
                    entry["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }
                        for call in message["tool_calls"]
                    ]
                out.append(entry)
                continue

            out.append({"role": "user", "content": message["content"]})

        return out

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=settings.max_tokens,
            messages=self._messages(system, messages),
            tools=self._tools(tools) if tools else None,
        )

        choice = response.choices[0].message
        calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=parse_arguments(call.function.arguments),
            )
            for call in (choice.tool_calls or [])
        ]
        return LLMResponse(text=(choice.content or "").strip(), tool_calls=calls, raw=response)
