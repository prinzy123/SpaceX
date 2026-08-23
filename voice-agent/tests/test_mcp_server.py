"""Tests for the MCP server that plugs this assistant into Claude."""

import json

from assistant.mcp_server import PROTOCOL_VERSION, handle


def test_initialize_echoes_the_clients_protocol_version():
    response = handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
    )
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["capabilities"]["tools"] == {"listChanged": False}


def test_initialize_falls_back_to_our_version():
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION


def test_notifications_get_no_reply():
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_uses_the_mcp_input_schema_key():
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert len(tools) > 5
    assert all("inputSchema" in tool for tool in tools)
    assert {"create_booking", "place_phone_call"} <= {tool["name"] for tool in tools}


def test_tools_call_returns_text_content(temp_store):
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "find_business", "arguments": {"query": "dentist"}},
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["isError"] is False
    assert payload["results"][0]["phone"]


def test_a_failed_tool_is_flagged_as_an_error(temp_store):
    response = handle(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope", "arguments": {}}}
    )
    assert response["result"]["isError"] is True


def test_unknown_method_returns_method_not_found():
    response = handle({"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
    assert response["error"]["code"] == -32601


def test_ping_is_answered():
    assert handle({"jsonrpc": "2.0", "id": 6, "method": "ping"})["result"] == {}
