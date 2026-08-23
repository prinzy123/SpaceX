"""Tests for the agent loop, using a scripted fake model (no API calls)."""

from assistant.agent import MAX_STEPS, Agent, PhoneAgent
from assistant.providers.base import LLMResponse, ToolCall


class ScriptedProvider:
    """Replays a fixed list of model responses so tests are deterministic."""

    name = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.calls_received = []

    def complete(self, system, messages, tools):
        self.calls_received.append({"system": system, "messages": list(messages), "tools": tools})
        if self.script:
            return self.script.pop(0)
        return LLMResponse(text="done")


def test_plain_reply_uses_no_tools():
    agent = Agent(provider=ScriptedProvider([LLMResponse(text="Hello.")]))
    turn = agent.send("hi")
    assert turn.reply == "Hello."
    assert turn.tool_calls == []
    assert turn.steps == 1


def test_tool_call_result_is_fed_back_to_the_model(temp_store):
    provider = ScriptedProvider(
        [
            LLMResponse(tool_calls=[ToolCall("1", "get_current_datetime", {})]),
            LLMResponse(text="It is Tuesday."),
        ]
    )
    turn = Agent(provider=provider).send("what day is it?")

    assert turn.reply == "It is Tuesday."
    assert turn.tool_calls[0]["name"] == "get_current_datetime"
    # The second model call must have been able to see the tool's output.
    second_call_messages = provider.calls_received[1]["messages"]
    assert second_call_messages[-1]["role"] == "tool"
    assert "iso" in second_call_messages[-1]["content"]


def test_multiple_tools_in_one_reply_all_run(temp_store):
    provider = ScriptedProvider(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall("1", "get_current_datetime", {}),
                    ToolCall("2", "find_business", {"query": "sushi"}),
                ]
            ),
            LLMResponse(text="Both done."),
        ]
    )
    turn = Agent(provider=provider).send("go")
    assert [c["name"] for c in turn.tool_calls] == ["get_current_datetime", "find_business"]


def test_failing_tool_does_not_crash_the_conversation(temp_store):
    provider = ScriptedProvider(
        [
            LLMResponse(tool_calls=[ToolCall("1", "cancel_booking", {"booking_id": "bk_nope"})]),
            LLMResponse(text="That booking does not exist."),
        ]
    )
    turn = Agent(provider=provider).send("cancel bk_nope")
    assert turn.tool_calls[0]["result"]["ok"] is False
    assert turn.reply == "That booking does not exist."


def test_runaway_loop_is_capped(temp_store):
    forever = [
        LLMResponse(tool_calls=[ToolCall(str(i), "get_current_datetime", {})]) for i in range(50)
    ]
    turn = Agent(provider=ScriptedProvider(forever)).send("loop forever")
    assert turn.steps == MAX_STEPS
    assert "stuck" in turn.reply


def test_tool_allowlist_is_respected():
    agent = Agent(provider=ScriptedProvider([]), allowed_tools=["list_bookings"])
    assert [s["name"] for s in agent.tool_schemas] == ["list_bookings"]


def test_history_is_kept_across_turns():
    provider = ScriptedProvider([LLMResponse(text="one"), LLMResponse(text="two")])
    agent = Agent(provider=provider)
    agent.send("first")
    agent.send("second")
    roles = [m["role"] for m in agent.messages]
    assert roles == ["user", "assistant", "user", "assistant"]


# ------------------------------------------------------------- phone agent
def test_phone_agent_detects_the_end_of_a_call():
    provider = ScriptedProvider([LLMResponse(text="Lovely, thank you. [[END_CALL]]")])
    agent = PhoneAgent("Mama Put", "book a table", provider=provider)
    spoken, finished = agent.listen("You're booked.")
    assert finished is True
    assert "[[END_CALL]]" not in spoken


def test_phone_agent_keeps_talking_until_told_otherwise():
    provider = ScriptedProvider([LLMResponse(text="Do you have 7pm?")])
    spoken, finished = PhoneAgent("A", "book", provider=provider).listen("Hello?")
    assert finished is False
    assert spoken == "Do you have 7pm?"


def test_phone_agent_gets_a_spoken_persona_and_few_tools():
    agent = PhoneAgent("Mama Put", "Book a table for 4", provider=ScriptedProvider([]))
    assert "AI assistant" in agent.system
    assert [s["name"] for s in agent.tool_schemas] == ["get_current_datetime"]


def test_result_line_is_parsed_from_the_transcript():
    transcript = [
        {"speaker": "human", "text": "Sure, 7pm works."},
        {"speaker": "agent", "text": "Great.\nRESULT: confirmed | Fri 4 Sep 19:00 | REF42\n[[END_CALL]]"},
    ]
    result = PhoneAgent.extract_result(transcript)
    assert result == {"status": "confirmed", "detail": "Fri 4 Sep 19:00", "reference": "REF42"}


def test_missing_result_line_is_unknown_not_a_crash():
    assert PhoneAgent.extract_result([{"speaker": "agent", "text": "bye"}])["status"] == "unknown"
