"""Tests for the phone webhooks and the REST API.

The phone tests matter most: a bug here means dead air on a live call with a
real receptionist, which is the worst failure this project can have.
"""

import pytest
from fastapi.testclient import TestClient

from assistant import server
from assistant.agent import PhoneAgent
from assistant.providers.base import LLMResponse

from tests.test_agent import ScriptedProvider


@pytest.fixture
def client(temp_store, monkeypatch):
    monkeypatch.setattr(server, "store", temp_store)
    monkeypatch.setattr(server, "_phone_sessions", {})
    monkeypatch.setattr(server, "_chat_sessions", {})
    return TestClient(server.app)


@pytest.fixture
def staged_call(temp_store):
    return temp_store.stage_call(
        to_number="+2348030000001", business_name="Mama Put", objective="Book a table for 4"
    )


def _use_script(monkeypatch, script):
    """Force any PhoneAgent the server builds to use a scripted model."""
    original = PhoneAgent.__init__

    def patched(self, business, objective, provider=None):
        original(self, business, objective, provider=ScriptedProvider(script))

    monkeypatch.setattr(PhoneAgent, "__init__", patched)


def test_health_reports_configuration(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert "telephony_ready" in body


# --------------------------------------------------------------- the call
def test_opening_line_discloses_the_ai_and_then_listens(client, staged_call):
    response = client.post(f"/voice/outbound?call_id={staged_call['id']}")
    assert response.status_code == 200
    assert "AI assistant" in response.text
    assert "<Gather" in response.text
    assert 'action="/voice/turn' in response.text


def test_unknown_call_id_hangs_up_politely(client):
    response = client.post("/voice/outbound?call_id=call_nope")
    assert "<Hangup/>" in response.text


def test_reply_is_spoken_and_the_call_continues(client, staged_call, monkeypatch, temp_store):
    _use_script(monkeypatch, [LLMResponse(text="Do you have seven pm?")])

    response = client.post(
        f"/voice/turn?call_id={staged_call['id']}", data={"SpeechResult": "Hello, Mama Put."}
    )
    assert "Do you have seven pm?" in response.text
    assert "<Gather" in response.text

    transcript = temp_store.calls.get(staged_call["id"])["transcript"]
    assert transcript[-2:] == [
        {"speaker": "human", "text": "Hello, Mama Put."},
        {"speaker": "agent", "text": "Do you have seven pm?"},
    ]


def test_end_token_hangs_up_and_confirms_the_booking(client, temp_store, monkeypatch):
    booking = temp_store.create_booking(
        business_name="Mama Put", kind="restaurant", starts_at="2026-09-04T19:00", party_size=4
    )
    call = temp_store.stage_call(
        to_number="+234", business_name="Mama Put", objective="Book 4", booking_id=booking["id"]
    )
    _use_script(
        monkeypatch,
        [LLMResponse(text="Wonderful, thank you.\nRESULT: confirmed | Fri 19:00 | REF42\n[[END_CALL]]")],
    )

    response = client.post(f"/voice/turn?call_id={call['id']}", data={"SpeechResult": "You're booked."})
    assert "<Hangup/>" in response.text
    assert "[[END_CALL]]" not in response.text  # never read the token out loud

    assert temp_store.calls.get(call["id"])["status"] == "completed"
    updated = temp_store.bookings.get(booking["id"])
    assert updated["status"] == "confirmed"
    assert updated["confirmation_ref"] == "REF42"


def test_silence_asks_them_to_repeat(client, staged_call):
    response = client.post(f"/voice/turn?call_id={staged_call['id']}", data={"SpeechResult": ""})
    assert "say it again" in response.text.lower()
    assert "retry=1" in response.text


def test_repeated_silence_eventually_hangs_up(client, staged_call):
    response = client.post(
        f"/voice/turn?call_id={staged_call['id']}&retry=2", data={"SpeechResult": ""}
    )
    assert "<Gather" not in response.text
    assert "<Hangup/>" in response.text


def test_a_model_crash_ends_the_call_gracefully(client, staged_call, monkeypatch):
    class Exploding:
        name = "boom"

        def complete(self, *_args, **_kwargs):
            raise RuntimeError("API is down")

    original = PhoneAgent.__init__
    monkeypatch.setattr(
        PhoneAgent,
        "__init__",
        lambda self, business, objective, provider=None: original(
            self, business, objective, provider=Exploding()
        ),
    )

    response = client.post(f"/voice/turn?call_id={staged_call['id']}", data={"SpeechResult": "Hi"})
    assert response.status_code == 200
    assert "<Hangup/>" in response.text
    assert "technical problem" in response.text


def test_xml_special_characters_are_escaped(client, staged_call, monkeypatch):
    _use_script(monkeypatch, [LLMResponse(text='Table for "Ada" & co <yes>?')])
    response = client.post(f"/voice/turn?call_id={staged_call['id']}", data={"SpeechResult": "hi"})
    assert "&amp;" in response.text and "&lt;yes&gt;" in response.text


def test_status_callback_finalises_the_call(client, staged_call, temp_store):
    client.post(f"/voice/status?call_id={staged_call['id']}")
    assert temp_store.calls.get(staged_call["id"])["status"] == "completed"


# ---------------------------------------------------------------- rest api
def test_message_endpoint_returns_a_reply(client, monkeypatch):
    from assistant import agent as agent_module

    monkeypatch.setattr(
        agent_module, "get_provider", lambda name=None: ScriptedProvider([LLMResponse(text="ok")])
    )
    monkeypatch.setattr(
        agent_module.Agent, "send", lambda self, text: agent_module.Turn(reply=f"heard: {text}")
    )
    body = client.post("/assistant/message", json={"message": "book a table"}).json()
    assert body["reply"] == "heard: book a table"
    assert body["session_id"] == "default"


def test_message_endpoint_rejects_an_empty_message(client):
    assert client.post("/assistant/message", json={"message": "  "}).status_code == 400


def test_api_key_is_enforced_when_configured(client, monkeypatch):
    from assistant.config import settings

    monkeypatch.setattr(settings, "server_api_key", "secret123")
    assert client.get("/bookings").status_code == 401
    assert client.get("/bookings", headers={"X-API-Key": "secret123"}).status_code == 200


def test_bookings_and_cancel_over_http(client, temp_store):
    booking = temp_store.create_booking(
        business_name="A", kind="restaurant", starts_at="2026-09-04T19:00"
    )
    assert len(client.get("/bookings").json()["bookings"]) == 1

    cancelled = client.post(f"/bookings/{booking['id']}/cancel", json={"reason": "busy"})
    assert cancelled.json()["booking"]["status"] == "cancelled"
    assert client.post("/bookings/bk_nope/cancel", json={}).status_code == 404


def test_approving_a_call_without_twilio_is_a_dry_run(client, staged_call):
    body = client.post(f"/calls/{staged_call['id']}/approve").json()
    assert body["ok"] is True and body["dry_run"] is True
