"""Tests for the format translation between our neutral messages and each API.

These are the fiddliest 60 lines in the project and the ones most likely to
break silently, so they are tested without touching the network. Calling the
static methods on the class means no API key is needed.
"""

import json

from assistant.providers.anthropic_provider import AnthropicProvider
from assistant.providers.base import ToolCall, parse_arguments
from assistant.providers.echo_provider import EchoProvider
from assistant.providers.openai_provider import OpenAIProvider

NEUTRAL = [
    {"role": "user", "content": "book a table"},
    {"role": "assistant", "content": "checking", "tool_calls": [ToolCall("t1", "list_bookings", {})]},
    {"role": "tool", "tool_call_id": "t1", "name": "list_bookings", "content": '{"ok": true}'},
]

SCHEMA = [{"name": "list_bookings", "description": "list", "parameters": {"type": "object", "properties": {}}}]


# ------------------------------------------------------------------- shared
def test_parse_arguments_handles_dict_string_and_junk():
    assert parse_arguments({"a": 1}) == {"a": 1}
    assert parse_arguments('{"a": 1}') == {"a": 1}
    assert parse_arguments("not json") == {}
    assert parse_arguments(None) == {}


# ------------------------------------------------------------------- claude
def test_claude_tool_schema_uses_input_schema_key():
    converted = AnthropicProvider._tools(SCHEMA)
    assert converted[0]["input_schema"] == SCHEMA[0]["parameters"]
    assert "parameters" not in converted[0]


def test_claude_tool_use_becomes_a_content_block():
    converted = AnthropicProvider._messages(NEUTRAL)
    assistant_blocks = converted[1]["content"]
    assert assistant_blocks[0] == {"type": "text", "text": "checking"}
    assert assistant_blocks[1]["type"] == "tool_use"
    assert assistant_blocks[1]["id"] == "t1"


def test_claude_tool_results_come_back_as_a_user_message():
    converted = AnthropicProvider._messages(NEUTRAL)
    assert converted[2]["role"] == "user"
    assert converted[2]["content"][0]["type"] == "tool_result"
    assert converted[2]["content"][0]["tool_use_id"] == "t1"


def test_claude_merges_parallel_tool_results_into_one_message():
    """Claude rejects two separate user messages of tool results in a row."""
    messages = [
        {"role": "user", "content": "go"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [ToolCall("a", "x", {}), ToolCall("b", "y", {})],
        },
        {"role": "tool", "tool_call_id": "a", "name": "x", "content": "1"},
        {"role": "tool", "tool_call_id": "b", "name": "y", "content": "2"},
    ]
    converted = AnthropicProvider._messages(messages)
    assert len(converted) == 3
    assert len(converted[2]["content"]) == 2


def test_claude_skips_an_empty_assistant_turn():
    """An assistant message with no text and no tools is invalid for the API."""
    converted = AnthropicProvider._messages(
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "", "tool_calls": []}]
    )
    assert len(converted) == 1


# ------------------------------------------------------------------- openai
def test_openai_puts_the_system_prompt_in_the_message_list():
    converted = OpenAIProvider._messages("be helpful", NEUTRAL)
    assert converted[0] == {"role": "system", "content": "be helpful"}


def test_openai_tool_arguments_are_json_encoded_strings():
    converted = OpenAIProvider._messages("s", NEUTRAL)
    call = converted[2]["tool_calls"][0]
    assert call["type"] == "function"
    assert json.loads(call["function"]["arguments"]) == {}


def test_openai_tool_results_use_the_tool_role():
    converted = OpenAIProvider._messages("s", NEUTRAL)
    assert converted[3]["role"] == "tool"
    assert converted[3]["tool_call_id"] == "t1"


def test_openai_wraps_tools_in_a_function_envelope():
    converted = OpenAIProvider._tools(SCHEMA)
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["parameters"] == SCHEMA[0]["parameters"]


# -------------------------------------------------------------------- echo
def test_echo_provider_needs_no_key_and_still_books():
    response = EchoProvider().complete(
        "s",
        [{"role": "user", "content": "book a table at Blue Fin tomorrow 8pm for 3 people"}],
        [{"name": "create_booking"}],
    )
    call = response.tool_calls[0]
    assert call.name == "create_booking"
    assert call.arguments["party_size"] == 3
    assert call.arguments["starts_at"].endswith("20:00")


def test_echo_provider_summarises_after_a_tool_runs():
    response = EchoProvider().complete("s", [{"role": "tool", "content": "{}"}], [])
    assert response.tool_calls == []
    assert "offline demo brain" in response.text.lower()


def test_echo_provider_explains_itself_when_confused():
    response = EchoProvider().complete("s", [{"role": "user", "content": "asdfgh"}], [])
    assert "book a table" in response.text
