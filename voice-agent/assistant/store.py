"""Dead-simple JSON storage for bookings, staged calls and your preferences.

A real product would use a database. A JSON file is easier to read, easier to
debug and perfectly fine for one person's calendar -- you can literally open
data/bookings.json in a text editor and see what your assistant did.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from assistant.config import settings

_LOCK = threading.Lock()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class JsonCollection:
    """A list of dictionaries persisted to one JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text() or "[]")
        except json.JSONDecodeError:
            # A corrupt file should never crash the assistant mid-conversation.
            backup = self.path.with_suffix(".corrupt.json")
            self.path.rename(backup)
            return []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=2, default=str))
        tmp.replace(self.path)

    def all(self) -> list[dict[str, Any]]:
        with _LOCK:
            return self._read()

    def add(self, row: dict[str, Any]) -> dict[str, Any]:
        with _LOCK:
            rows = self._read()
            rows.append(row)
            self._write(rows)
        return row

    def get(self, row_id: str) -> dict[str, Any] | None:
        return next((r for r in self.all() if r.get("id") == row_id), None)

    def update(self, row_id: str, **changes: Any) -> dict[str, Any] | None:
        with _LOCK:
            rows = self._read()
            for row in rows:
                if row.get("id") == row_id:
                    row.update(changes)
                    row["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    self._write(rows)
                    return row
        return None


class Store:
    """Everything the assistant remembers between conversations."""

    def __init__(self, data_dir: Path | None = None) -> None:
        base = Path(data_dir) if data_dir else settings.data_dir
        base.mkdir(parents=True, exist_ok=True)
        self.bookings = JsonCollection(base / "bookings.json")
        self.calls = JsonCollection(base / "calls.json")
        self._prefs_path = base / "preferences.json"

    # ---------------------------------------------------------------- bookings
    def create_booking(
        self,
        *,
        business_name: str,
        kind: str,
        starts_at: str,
        party_size: int = 1,
        duration_minutes: int = 60,
        phone: str = "",
        notes: str = "",
        status: str = "requested",
    ) -> dict[str, Any]:
        booking = {
            "id": _new_id("bk"),
            "business_name": business_name,
            "kind": kind,
            "starts_at": starts_at,
            "duration_minutes": duration_minutes,
            "party_size": party_size,
            "phone": phone,
            "notes": notes,
            "status": status,
            "confirmation_ref": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        return self.bookings.add(booking)

    def upcoming(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = [b for b in self.bookings.all() if b.get("status") != "cancelled"]
        rows.sort(key=lambda b: str(b.get("starts_at", "")))
        return rows[:limit]

    def conflicts(self, starts_at: str, duration_minutes: int = 60) -> list[dict[str, Any]]:
        """Bookings that overlap the requested window."""
        try:
            start = datetime.fromisoformat(starts_at)
        except ValueError:
            return []
        end = start + timedelta(minutes=duration_minutes)

        clashes = []
        for booking in self.bookings.all():
            if booking.get("status") == "cancelled":
                continue
            try:
                other_start = datetime.fromisoformat(str(booking["starts_at"]))
            except (ValueError, KeyError):
                continue
            other_end = other_start + timedelta(minutes=int(booking.get("duration_minutes", 60)))
            if start < other_end and other_start < end:
                clashes.append(booking)
        return clashes

    # ------------------------------------------------------------------- calls
    def stage_call(
        self,
        *,
        to_number: str,
        business_name: str,
        objective: str,
        booking_id: str = "",
        status: str = "awaiting_approval",
    ) -> dict[str, Any]:
        call = {
            "id": _new_id("call"),
            "to_number": to_number,
            "business_name": business_name,
            "objective": objective,
            "booking_id": booking_id,
            "status": status,
            "transcript": [],
            "outcome": "",
            "provider_sid": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        return self.calls.add(call)

    def append_turn(self, call_id: str, speaker: str, text: str) -> None:
        call = self.calls.get(call_id)
        if not call:
            return
        transcript = list(call.get("transcript", []))
        transcript.append({"speaker": speaker, "text": text})
        self.calls.update(call_id, transcript=transcript)

    # ------------------------------------------------------------- preferences
    def preferences(self) -> dict[str, str]:
        if not self._prefs_path.exists():
            return {}
        try:
            return json.loads(self._prefs_path.read_text() or "{}")
        except json.JSONDecodeError:
            return {}

    def remember(self, key: str, value: str) -> dict[str, str]:
        with _LOCK:
            prefs = self.preferences()
            prefs[key] = value
            self._prefs_path.parent.mkdir(parents=True, exist_ok=True)
            self._prefs_path.write_text(json.dumps(prefs, indent=2))
        return prefs


store = Store()
