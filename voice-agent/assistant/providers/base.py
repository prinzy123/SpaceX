"""The contract every "brain" must satisfy.

The agent loop never imports anthropic or openai directly. It only talks to an
LLMProvider, so switching from Claude to GPT is a one-word change in .env.

Message format used everywhere inside this project (provider-neutral):

    {"role": "user",      "content": "book me a table"}
    {"role": "assistant", "content": "on it", "tool_calls": [ToolCall, ...]}
    {"role": "tool",      "tool_call_id": "abc", "name": "create_booking",
     "content": "{\"ok\": true}"}

Each provider translates that into its own wire format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """The model asking us to run one of its tools."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """One reply from the model: some text, and/or some tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(Protocol):
    name: str

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Send the conversation to the model and return its next move."""
        ...


def parse_arguments(raw: Any) -> dict[str, Any]:
    """Models occasionally hand back arguments as a JSON string. Normalise it."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {}
    return {}


def get_provider(name: str | None = None) -> LLMProvider:
    """Factory. `name` is "claude", "openai" or "echo"."""
    from assistant.config import settings

    chosen = (name or settings.provider or "claude").lower()

    if chosen in {"claude", "anthropic"}:
        from assistant.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if chosen in {"openai", "chatgpt", "gpt"}:
        from assistant.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if chosen in {"echo", "offline", "demo", "fake"}:
        from assistant.providers.echo_provider import EchoProvider

        return EchoProvider()

    raise ValueError(
        f"Unknown LLM_PROVIDER {chosen!r}. Use 'claude', 'openai' or 'echo'."
    )
