"""Making real phone calls, via Twilio.

Twilio is the phone company for software. You buy a number, and when your code
says "call +234...", Twilio dials it and then asks YOUR server what to say. The
conversation flows like this:

    your code -> twilio: please dial this number
    twilio    -> callee: *ring ring*
    callee picks up
    twilio    -> your server (/voice/outbound): they answered, what do I say?
    your server -> twilio: <Say>Hi, I'm an AI assistant...</Say><Gather/>
    callee speaks
    twilio    -> your server (/voice/turn): they said "sure, what time?"
    ...repeat until the agent says goodbye

If Twilio is not configured, everything below runs in DRY RUN mode: it logs what
it would have done and returns a fake id, so you can build and test for free.
"""

from __future__ import annotations

import logging
from typing import Any

from assistant.config import settings
from assistant.store import store

log = logging.getLogger("assistant.telephony")


def _client() -> Any:
    from twilio.rest import Client

    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def dial(call_id: str) -> dict[str, Any]:
    """Actually ring the number for a staged call."""
    call = store.calls.get(call_id)
    if not call:
        return {"ok": False, "error": f"No staged call with id {call_id}"}

    if not settings.telephony_ready:
        store.calls.update(call_id, status="dry_run", outcome="Twilio not configured.")
        log.warning("DRY RUN: would have called %s for %s", call["to_number"], call["objective"])
        return {
            "ok": True,
            "dry_run": True,
            "call_id": call_id,
            "message": (
                "Phone calling is not configured, so nothing was dialled. "
                f"Missing: {', '.join(settings.missing_telephony())}. "
                "See docs/03-phone-calls.md."
            ),
        }

    base = settings.public_base_url
    try:
        twilio_call = _client().calls.create(
            to=call["to_number"],
            from_=settings.twilio_from_number,
            url=f"{base}/voice/outbound?call_id={call_id}",
            status_callback=f"{base}/voice/status?call_id={call_id}",
            status_callback_event=["completed"],
            method="POST",
        )
    except Exception as exc:  # noqa: BLE001 - surface the reason to the model
        store.calls.update(call_id, status="failed", outcome=str(exc))
        return {"ok": False, "error": f"Twilio refused the call: {exc}"}

    store.calls.update(call_id, status="dialing", provider_sid=twilio_call.sid)
    return {"ok": True, "call_id": call_id, "sid": twilio_call.sid, "status": "dialing"}


def approve_and_dial(call_id: str) -> dict[str, Any]:
    """What the owner's 'yes' triggers."""
    call = store.calls.get(call_id)
    if not call:
        return {"ok": False, "error": f"No staged call with id {call_id}"}
    if call["status"] not in {"awaiting_approval", "failed", "dry_run"}:
        return {"ok": False, "error": f"Call is already {call['status']}."}
    store.calls.update(call_id, status="approved")
    return dial(call_id)


def send_sms(to_number: str, body: str) -> dict[str, Any]:
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        log.warning("DRY RUN sms to %s: %s", to_number, body)
        return {"ok": True, "dry_run": True, "message": f"Would have texted {to_number}: {body}"}
    try:
        message = _client().messages.create(
            to=to_number, from_=settings.twilio_from_number, body=body
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Could not send SMS: {exc}"}
    return {"ok": True, "sid": message.sid}
