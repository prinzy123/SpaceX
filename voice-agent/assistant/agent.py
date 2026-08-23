"""The agent loop.

This is the whole idea of an "AI agent" in about 40 lines:

    1. Send the conversation + the tool list to the model.
    2. If the model replies with text -> show it to the user. Done.
    3. If the model asks for a tool -> run it, append the result, go to step 1.

Everything else in this project is plumbing around this loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from assistant import prompts, tools
from assistant.providers import LLMProvider, get_provider

MAX_STEPS = 8  # stops a confused model from looping forever (and burning money)


@dataclass
class Turn:
    """What came out of one exchange with the assistant."""

    reply: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    steps: int = 0


class Agent:
    """A conversation with a tool-using model.

    Keep one Agent per conversation -- it holds the message history.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        system: str | None = None,
        allowed_tools: list[str] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.provider = provider or get_provider()
        self.system = system or prompts.assistant_system()
        self.messages: list[dict[str, Any]] = []
        self.on_event = on_event or (lambda kind, payload: None)

        if allowed_tools is None:
            self.tool_schemas = tools.schemas()
        else:
            allowed = set(allowed_tools)
            self.tool_schemas = [s for s in tools.schemas() if s["name"] in allowed]

    def send(self, user_message: str) -> Turn:
        """Say something to the assistant and get its reply."""
        self.messages.append({"role": "user", "content": user_message})
        return self._run()

    def _run(self) -> Turn:
        used: list[dict[str, Any]] = []

        for step in range(1, MAX_STEPS + 1):
            response = self.provider.complete(self.system, self.messages, self.tool_schemas)

            self.messages.append(
                {
                    "role": "assistant",
                    "content": response.text,
                    "tool_calls": response.tool_calls,
                }
            )

            if not response.wants_tools:
                self.on_event("reply", {"text": response.text})
                return Turn(reply=response.text, tool_calls=used, steps=step)

            for call in response.tool_calls:
                self.on_event("tool_start", {"name": call.name, "arguments": call.arguments})
                result = tools.run(call.name, call.arguments)
                self.on_event("tool_end", {"name": call.name, "result": result})

                used.append({"name": call.name, "arguments": call.arguments, "result": result})
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(result, default=str),
                    }
                )

        return Turn(
            reply=(
                "I got stuck repeating myself, so I stopped to avoid wasting your "
                "credits. Try asking me in a more specific way."
            ),
            tool_calls=used,
            steps=MAX_STEPS,
        )


class PhoneAgent(Agent):
    """The version that talks to a stranger on a live call.

    It gets a different personality (short spoken sentences, AI disclosure) and
    a much smaller set of tools -- you do not want it booking or texting while
    it is mid-sentence with a receptionist.
    """

    END_TOKEN = "[[END_CALL]]"

    def __init__(
        self,
        business: str,
        objective: str,
        provider: LLMProvider | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            system=prompts.phone_system(business, objective),
            allowed_tools=["get_current_datetime"],
        )
        self.business = business
        self.objective = objective

    def listen(self, heard: str) -> tuple[str, bool]:
        """Feed in what the other person said. Returns (what to say, hang up?)."""
        turn = self.send(heard)
        spoken = turn.reply
        finished = self.END_TOKEN in spoken
        spoken = spoken.replace(self.END_TOKEN, "").strip()
        return spoken, finished

    @staticmethod
    def extract_result(transcript: list[dict[str, str]]) -> dict[str, str]:
        """Pull the RESULT: line the phone prompt asks the model to emit."""
        for turn in reversed(transcript):
            for line in turn.get("text", "").splitlines():
                if line.strip().upper().startswith("RESULT:"):
                    parts = [p.strip() for p in line.split(":", 1)[1].split("|")]
                    status = parts[0].lower() if parts else "unknown"
                    return {
                        "status": status,
                        "detail": parts[1] if len(parts) > 1 else "",
                        "reference": parts[2] if len(parts) > 2 else "",
                    }
        return {"status": "unknown", "detail": "", "reference": ""}
