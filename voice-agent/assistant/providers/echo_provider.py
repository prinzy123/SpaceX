"""A tiny offline "brain" so you can try everything with NO API key.

It is not smart -- it matches keywords with regular expressions. Its only job
is to prove your installation works and to let you see the tool loop in action
before you spend a cent. Switch to Claude or GPT for anything real.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from assistant.providers.base import LLMResponse, ToolCall

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _next_datetime(text: str, now: datetime | None = None) -> datetime:
    """Turn 'friday 7pm' / 'tomorrow at 19:30' into a real datetime."""
    now = now or datetime.now()
    target = now.replace(second=0, microsecond=0)

    if "tomorrow" in text:
        target += timedelta(days=1)
    else:
        for index, day in enumerate(_WEEKDAYS):
            if day in text:
                ahead = (index - now.weekday()) % 7 or 7
                target += timedelta(days=ahead)
                break

    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    hour, minute = 19, 0
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    return target.replace(hour=min(hour, 23), minute=minute)


class EchoProvider:
    name = "echo"

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        # If the last thing that happened was a tool running, summarise and stop.
        if messages and messages[-1]["role"] == "tool":
            return LLMResponse(
                text=(
                    "Done. (You are running the offline demo brain, so this reply is "
                    "canned. Set LLM_PROVIDER=claude in .env for real conversation.)"
                )
            )

        user_text = ""
        for message in reversed(messages):
            if message["role"] == "user" and isinstance(message.get("content"), str):
                user_text = message["content"].lower()
                break

        available = {tool["name"] for tool in tools}

        def call(name: str, **arguments: Any) -> LLMResponse:
            return LLMResponse(
                text="",
                tool_calls=[ToolCall(id=f"echo_{uuid.uuid4().hex[:8]}", name=name, arguments=arguments)],
            )

        if any(word in user_text for word in ("my bookings", "what do i have", "list", "schedule")):
            if "list_bookings" in available:
                return call("list_bookings")

        if "cancel" in user_text and "cancel_booking" in available:
            match = re.search(r"\bbk_\w+", user_text)
            if match:
                return call("cancel_booking", booking_id=match.group(0))
            return LLMResponse(text="Which booking? Give me its id, e.g. bk_1a2b3c4d5e.")

        if any(word in user_text for word in ("book", "reserve", "table", "appointment", "haircut")):
            if "create_booking" not in available:
                return LLMResponse(text="I cannot make bookings in this mode.")
            party = re.search(r"(\d+)\s*(?:people|persons?|guests?|pax)", user_text)
            name = re.search(r"\bat\s+([a-z0-9' &]+?)(?:\s+(?:on|for|at|tomorrow|next)\b|$)", user_text)
            return call(
                "create_booking",
                business_name=(name.group(1).strip().title() if name else "Unnamed venue"),
                kind="restaurant" if "table" in user_text or "restaurant" in user_text else "appointment",
                starts_at=_next_datetime(user_text).isoformat(timespec="minutes"),
                party_size=int(party.group(1)) if party else 2,
                notes="Created by the offline demo brain.",
            )

        return LLMResponse(
            text=(
                "Offline demo brain here. I understand a few phrases: "
                "'book a table at Mama Put tomorrow 7pm for 4 people', "
                "'list my bookings', 'cancel bk_xxx'. "
                "Add an ANTHROPIC_API_KEY and set LLM_PROVIDER=claude for the real thing."
            )
        )
