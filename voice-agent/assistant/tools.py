"""Everything the assistant is allowed to DO.

A "tool" is a normal Python function plus a description of its arguments. We
hand those descriptions to the model; the model replies "run create_booking
with these arguments"; we run it and hand back the result. That loop is all an
AI agent really is.

To give your assistant a new power, write a function here and decorate it. It
becomes available to Claude, to ChatGPT, to the phone agent and to the MCP
server automatically -- no other file needs editing.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from assistant.config import settings
from assistant.store import store

ToolFn = Callable[..., dict[str, Any]]

REGISTRY: dict[str, dict[str, Any]] = {}


def tool(description: str, parameters: dict[str, Any]) -> Callable[[ToolFn], ToolFn]:
    """Register a function as a tool the model can call."""

    def decorator(fn: ToolFn) -> ToolFn:
        REGISTRY[fn.__name__] = {
            "name": fn.__name__,
            "description": description,
            "parameters": parameters,
            "fn": fn,
        }
        return fn

    return decorator


def schemas(exclude: set[str] | None = None) -> list[dict[str, Any]]:
    """The tool list to send to the model (no Python functions in it)."""
    exclude = exclude or set()
    return [
        {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
        for t in REGISTRY.values()
        if t["name"] not in exclude
    ]


def run(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name. Never raises -- the model gets the error instead."""
    entry = REGISTRY.get(name)
    if entry is None:
        return {"ok": False, "error": f"No such tool: {name}"}
    try:
        result = entry["fn"](**arguments)
    except TypeError as exc:
        return {"ok": False, "error": f"Wrong arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - a crash here must not kill the call
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return result if isinstance(result, dict) else {"ok": True, "result": result}


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


_STR = {"type": "string"}
_INT = {"type": "integer"}


# --------------------------------------------------------------------- time
@tool(
    "Get the current date and time. Call this before working out any relative "
    "date such as 'tomorrow', 'next Friday' or 'in two hours'.",
    _obj({}),
)
def get_current_datetime() -> dict[str, Any]:
    now = datetime.now()
    return {
        "ok": True,
        "iso": now.isoformat(timespec="minutes"),
        "human": now.strftime("%A %d %B %Y, %H:%M"),
        "timezone": settings.timezone,
    }


# ---------------------------------------------------------------- directory
def _directory() -> list[dict[str, Any]]:
    path = Path(settings.data_dir) / "businesses.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


@tool(
    "Look up a business (restaurant, clinic, salon, garage...) to get its phone "
    "number before calling it. Searches the local address book in "
    "data/businesses.json.",
    _obj(
        {
            "query": {**_STR, "description": "Name or type, e.g. 'Mama Put' or 'dentist'"},
            "city": {**_STR, "description": "Optional city filter"},
        },
        ["query"],
    ),
)
def find_business(query: str, city: str = "") -> dict[str, Any]:
    needle = query.lower().strip()
    matches = [
        row
        for row in _directory()
        if (
            needle in row.get("name", "").lower()
            or needle in row.get("category", "").lower()
            or any(needle in tag.lower() for tag in row.get("tags", []))
        )
        and (not city or city.lower() in row.get("city", "").lower())
    ]
    if not matches:
        return {
            "ok": False,
            "error": f"Nothing matching {query!r} in the address book.",
            "hint": "Add it to data/businesses.json, or ask the owner for the number.",
        }
    return {"ok": True, "count": len(matches), "results": matches[:5]}


# ----------------------------------------------------------------- bookings
@tool(
    "Check whether a time slot is free in the owner's calendar. Always call this "
    "before create_booking.",
    _obj(
        {
            "starts_at": {**_STR, "description": "ISO datetime, e.g. 2026-09-04T19:00"},
            "duration_minutes": {**_INT, "description": "Defaults to 60"},
        },
        ["starts_at"],
    ),
)
def check_availability(starts_at: str, duration_minutes: int = 60) -> dict[str, Any]:
    clashes = store.conflicts(starts_at, duration_minutes)
    return {
        "ok": True,
        "free": not clashes,
        "conflicts": [
            {"id": c["id"], "business_name": c["business_name"], "starts_at": c["starts_at"]}
            for c in clashes
        ],
    }


@tool(
    "Record a booking, reservation or appointment. Status starts as 'requested'; "
    "it becomes 'confirmed' only when the venue actually confirms it.",
    _obj(
        {
            "business_name": {**_STR, "description": "Where the booking is"},
            "kind": {
                "type": "string",
                "enum": ["restaurant", "appointment", "hotel", "travel", "service", "other"],
            },
            "starts_at": {**_STR, "description": "ISO datetime, e.g. 2026-09-04T19:00"},
            "party_size": _INT,
            "duration_minutes": _INT,
            "phone": {**_STR, "description": "Venue phone number if known"},
            "notes": {**_STR, "description": "Special requests, table preference, etc."},
        },
        ["business_name", "kind", "starts_at"],
    ),
)
def create_booking(
    business_name: str,
    kind: str,
    starts_at: str,
    party_size: int = 1,
    duration_minutes: int = 60,
    phone: str = "",
    notes: str = "",
) -> dict[str, Any]:
    clashes = store.conflicts(starts_at, duration_minutes)
    booking = store.create_booking(
        business_name=business_name,
        kind=kind,
        starts_at=starts_at,
        party_size=party_size,
        duration_minutes=duration_minutes,
        phone=phone,
        notes=notes,
    )
    return {
        "ok": True,
        "booking": booking,
        "warning": (
            f"Overlaps {len(clashes)} existing booking(s)." if clashes else ""
        ),
    }


@tool("List the owner's upcoming bookings.", _obj({"limit": _INT}))
def list_bookings(limit: int = 20) -> dict[str, Any]:
    rows = store.upcoming(limit)
    return {"ok": True, "count": len(rows), "bookings": rows}


@tool(
    "Mark a booking as confirmed, usually after a phone call succeeded.",
    _obj(
        {"booking_id": _STR, "confirmation_ref": {**_STR, "description": "Reference number"}},
        ["booking_id"],
    ),
)
def confirm_booking(booking_id: str, confirmation_ref: str = "") -> dict[str, Any]:
    row = store.bookings.update(booking_id, status="confirmed", confirmation_ref=confirmation_ref)
    if not row:
        return {"ok": False, "error": f"No booking with id {booking_id}"}
    return {"ok": True, "booking": row}


@tool(
    "Cancel a booking.",
    _obj({"booking_id": _STR, "reason": _STR}, ["booking_id"]),
)
def cancel_booking(booking_id: str, reason: str = "") -> dict[str, Any]:
    row = store.bookings.update(booking_id, status="cancelled", notes=reason)
    if not row:
        return {"ok": False, "error": f"No booking with id {booking_id}"}
    return {"ok": True, "booking": row}


@tool(
    "Change the time, size or notes of an existing booking.",
    _obj(
        {"booking_id": _STR, "starts_at": _STR, "party_size": _INT, "notes": _STR},
        ["booking_id"],
    ),
)
def update_booking(
    booking_id: str, starts_at: str = "", party_size: int = 0, notes: str = ""
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if starts_at:
        changes["starts_at"] = starts_at
    if party_size:
        changes["party_size"] = party_size
    if notes:
        changes["notes"] = notes
    if not changes:
        return {"ok": False, "error": "Nothing to change."}
    row = store.bookings.update(booking_id, **changes)
    if not row:
        return {"ok": False, "error": f"No booking with id {booking_id}"}
    return {"ok": True, "booking": row}


# -------------------------------------------------------------------- calls
@tool(
    "Call a business by phone to arrange something. Give a complete objective "
    "including fallbacks, because the agent on the call cannot ask you mid-call. "
    "Example: 'Book a table for 4 on Friday 19:00 under Ada. If full, take "
    "anything 18:30-20:30.'",
    _obj(
        {
            "to_number": {**_STR, "description": "E.164 number, e.g. +2348012345678"},
            "business_name": _STR,
            "objective": {**_STR, "description": "What the call must achieve, with fallbacks"},
            "booking_id": {**_STR, "description": "Link the call to a booking, if any"},
        },
        ["to_number", "business_name", "objective"],
    ),
)
def place_phone_call(
    to_number: str, business_name: str, objective: str, booking_id: str = ""
) -> dict[str, Any]:
    from assistant import telephony

    call = store.stage_call(
        to_number=to_number,
        business_name=business_name,
        objective=objective,
        booking_id=booking_id,
        status="awaiting_approval" if settings.require_call_approval else "dialing",
    )

    if settings.require_call_approval:
        return {
            "ok": True,
            "status": "awaiting_approval",
            "call_id": call["id"],
            "message": (
                f"Call to {business_name} ({to_number}) is staged and waiting for "
                "the owner to approve it. Tell them so they can say yes."
            ),
        }

    return telephony.dial(call["id"])


@tool("Show staged and completed calls, with transcripts.", _obj({"limit": _INT}))
def list_calls(limit: int = 10) -> dict[str, Any]:
    rows = store.calls.all()[-limit:]
    return {"ok": True, "count": len(rows), "calls": rows}


@tool(
    "Send an SMS, e.g. a confirmation to the owner or a text to a venue.",
    _obj({"to_number": _STR, "body": _STR}, ["to_number", "body"]),
)
def send_sms(to_number: str, body: str) -> dict[str, Any]:
    from assistant import telephony

    return telephony.send_sms(to_number, body)


# -------------------------------------------------------------- preferences
@tool(
    "Remember a lasting fact about the owner so you never have to ask again "
    "(diet, allergies, favourite venues, usual party size, home address area).",
    _obj(
        {
            "key": {**_STR, "description": "Short label, e.g. 'diet' or 'seat_preference'"},
            "value": _STR,
        },
        ["key", "value"],
    ),
)
def remember_preference(key: str, value: str) -> dict[str, Any]:
    return {"ok": True, "preferences": store.remember(key, value)}


@tool("Recall everything you know about the owner's preferences.", _obj({}))
def get_preferences() -> dict[str, Any]:
    return {"ok": True, "preferences": store.preferences()}
