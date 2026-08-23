"""The web server. It does two separate jobs.

JOB 1 -- run the phone conversations (/voice/*).
    Twilio calls these URLs while a call is in progress. They must return TwiML
    (Twilio's little XML dialect) telling Twilio what to say and when to listen.

JOB 2 -- expose the assistant over HTTP (/assistant/*, /bookings, /calls).
    This is what a ChatGPT Custom GPT, a phone shortcut, or any other app talks
    to. Protected by the SERVER_API_KEY header, because it will be on the open
    internet while ngrok is running.

Run it with:   uvicorn assistant.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
from typing import Any
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response

from assistant import prompts, telephony
from assistant.agent import Agent, PhoneAgent
from assistant.config import settings
from assistant.store import store

log = logging.getLogger("assistant.server")

app = FastAPI(
    title="Personal Voice Assistant",
    version="1.0.0",
    description="Books, reserves and phones things on your behalf.",
)

# Live conversations, kept in memory. A restart loses them, which is fine for a
# personal assistant -- a real deployment would use Redis.
_chat_sessions: dict[str, Agent] = {}
_phone_sessions: dict[str, PhoneAgent] = {}


# --------------------------------------------------------------------- auth
def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Protects the non-Twilio routes."""
    if not settings.server_api_key:
        return  # not configured -> open, fine for localhost-only use
    if x_api_key != settings.server_api_key:
        raise HTTPException(status_code=401, detail="Bad or missing X-API-Key header.")


async def verify_twilio(request: Request) -> None:
    """Confirms a /voice/* request really came from Twilio and not a stranger."""
    if not settings.twilio_auth_token or not settings.public_base_url:
        return
    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    url = f"{settings.public_base_url}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    validator = RequestValidator(settings.twilio_auth_token)
    if not validator.validate(url, dict(form), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")


# --------------------------------------------------------------------- twiml
def _twiml(*parts: str) -> Response:
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response>{"".join(parts)}</Response>'
    return Response(content=body, media_type="application/xml")


def _say(text: str) -> str:
    return f'<Say voice="Polly.Joanna">{escape(text)}</Say>'


def _gather(action: str, prompt: str = "") -> str:
    inner = _say(prompt) if prompt else ""
    return (
        f'<Gather input="speech" speechTimeout="auto" action="{escape(action)}" '
        f'method="POST" language="en-US">{inner}</Gather>'
    )


def _phone_agent(call_id: str) -> PhoneAgent | None:
    """Get the live agent for a call, rebuilding it if the server restarted."""
    if call_id in _phone_sessions:
        return _phone_sessions[call_id]

    call = store.calls.get(call_id)
    if not call:
        return None

    agent = PhoneAgent(business=call["business_name"], objective=call["objective"])
    for turn in call.get("transcript", []):
        role = "assistant" if turn["speaker"] == "agent" else "user"
        agent.messages.append({"role": role, "content": turn["text"], "tool_calls": []})
    _phone_sessions[call_id] = agent
    return agent


# ----------------------------------------------------------- voice webhooks
@app.post("/voice/outbound", dependencies=[Depends(verify_twilio)])
async def voice_outbound(call_id: str) -> Response:
    """They picked up. Say hello (and disclose that we're an AI)."""
    call = store.calls.get(call_id)
    if not call:
        return _twiml(_say("Sorry, wrong number. Goodbye."), "<Hangup/>")

    store.calls.update(call_id, status="in_progress")
    opening = prompts.opening_line(call["business_name"], call["objective"])
    store.append_turn(call_id, "agent", opening)

    return _twiml(
        _gather(f"/voice/turn?call_id={call_id}", opening),
        _say("Sorry, I didn't catch that. I'll try again later. Goodbye."),
        "<Hangup/>",
    )


MAX_MISHEARD = 2  # after this many unintelligible turns, hang up politely


@app.post("/voice/turn", dependencies=[Depends(verify_twilio)])
async def voice_turn(call_id: str, request: Request, retry: int = 0) -> Response:
    """They said something. Think, then reply out loud."""
    form = await request.form()
    heard = str(form.get("SpeechResult", "")).strip()

    # Nothing intelligible. Ask once or twice, then stop -- never loop forever
    # on a bad line, because every loop is a paid Twilio minute.
    if not heard:
        if retry >= MAX_MISHEARD:
            return _twiml(
                _say("I'm having trouble hearing you. I'll try again later. Goodbye."),
                "<Hangup/>",
            )
        return _twiml(
            _gather(
                f"/voice/turn?call_id={call_id}&retry={retry + 1}",
                "Sorry, I missed that. Could you say it again?",
            ),
            _say("I'll call back another time. Thank you, goodbye."),
            "<Hangup/>",
        )

    agent = _phone_agent(call_id)
    if agent is None:
        return _twiml(_say("Sorry, something went wrong on my end. Goodbye."), "<Hangup/>")

    store.append_turn(call_id, "human", heard)
    try:
        spoken, finished = agent.listen(heard)
    except Exception as exc:  # noqa: BLE001 - never leave dead air on a live call
        log.exception("phone agent failed: %s", exc)
        return _twiml(
            _say("I'm having a technical problem. I'll call back. Thank you, goodbye."),
            "<Hangup/>",
        )

    store.append_turn(call_id, "agent", spoken)

    if finished:
        _finalise(call_id)
        return _twiml(_say(spoken or "Thank you, goodbye."), "<Hangup/>")

    return _twiml(
        _gather(f"/voice/turn?call_id={call_id}&retry=0", spoken),
        _say("Are you still there? I'll follow up later. Goodbye."),
        "<Hangup/>",
    )


@app.post("/voice/status", dependencies=[Depends(verify_twilio)])
async def voice_status(call_id: str) -> dict[str, Any]:
    """Twilio tells us the call ended (including if nobody answered)."""
    _finalise(call_id)
    _phone_sessions.pop(call_id, None)
    return {"ok": True}


@app.post("/voice/incoming", dependencies=[Depends(verify_twilio)])
async def voice_incoming(request: Request) -> Response:
    """YOU calling YOUR assistant's number -- a hands-free personal assistant."""
    form = await request.form()
    heard = str(form.get("SpeechResult", "")).strip()
    caller = str(form.get("From", "unknown"))

    if not heard:
        return _twiml(
            _gather("/voice/incoming", f"Hello {settings.owner_name}. What can I do for you?"),
            _say("Goodbye."),
            "<Hangup/>",
        )

    session_id = f"phone:{caller}"
    agent = _chat_sessions.setdefault(session_id, Agent())
    turn = agent.send(heard)

    return _twiml(
        _gather("/voice/incoming", turn.reply or "Done. Anything else?"),
        _say("Goodbye."),
        "<Hangup/>",
    )


def _finalise(call_id: str) -> None:
    """Write the call's outcome back onto the booking it belongs to."""
    call = store.calls.get(call_id)
    if not call or call.get("status") == "completed":
        return

    result = PhoneAgent.extract_result(call.get("transcript", []))
    store.calls.update(call_id, status="completed", outcome=f"{result['status']}: {result['detail']}")

    if call.get("booking_id") and result["status"] == "confirmed":
        store.bookings.update(
            call["booking_id"], status="confirmed", confirmation_ref=result["reference"]
        )


# --------------------------------------------------------------- rest api
@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "provider": settings.provider,
        "telephony_ready": settings.telephony_ready,
        "missing_for_calls": settings.missing_telephony(),
    }


@app.post("/assistant/message", dependencies=[Depends(require_api_key)])
async def assistant_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Talk to the assistant. This is the endpoint a ChatGPT Custom GPT uses."""
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")

    session_id = str(payload.get("session_id") or "default")
    agent = _chat_sessions.setdefault(session_id, Agent())
    turn = agent.send(message)

    return {
        "reply": turn.reply,
        "session_id": session_id,
        "actions_taken": [
            {"tool": c["name"], "ok": c["result"].get("ok", False)} for c in turn.tool_calls
        ],
    }


@app.get("/bookings", dependencies=[Depends(require_api_key)])
async def get_bookings(limit: int = 20) -> dict[str, Any]:
    return {"bookings": store.upcoming(limit)}


@app.post("/bookings/{booking_id}/cancel", dependencies=[Depends(require_api_key)])
async def cancel(booking_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    reason = (payload or {}).get("reason", "")
    row = store.bookings.update(booking_id, status="cancelled", notes=reason)
    if not row:
        raise HTTPException(status_code=404, detail="No such booking.")
    return {"booking": row}


@app.get("/calls", dependencies=[Depends(require_api_key)])
async def get_calls(limit: int = 20) -> dict[str, Any]:
    return {"calls": store.calls.all()[-limit:]}


@app.post("/calls/{call_id}/approve", dependencies=[Depends(require_api_key)])
async def approve_call(call_id: str) -> dict[str, Any]:
    """The human 'yes' that lets a staged call actually dial."""
    result = telephony.approve_and_dial(call_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Could not dial."))
    return result
