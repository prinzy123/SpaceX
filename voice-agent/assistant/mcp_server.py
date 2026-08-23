"""Plug this assistant straight into Claude Desktop or Claude Code.

MCP (Model Context Protocol) is how Claude picks up new tools. Claude launches
this file, they talk JSON back and forth over stdin/stdout, and suddenly Claude
itself can book tables and place calls -- no separate chat window, no API key of
your own needed, because Claude is already the brain.

This is a hand-written MCP server: about 100 lines, zero extra packages.

Wire it up (Claude Desktop -> Settings -> Developer -> Edit Config):

    {
      "mcpServers": {
        "assistant": {
          "command": "python3",
          "args": ["-m", "assistant.mcp_server"],
          "cwd": "/absolute/path/to/voice-agent"
        }
      }
    }

Or from a terminal, for Claude Code:
    claude mcp add assistant -- python3 -m assistant.mcp_server
"""

from __future__ import annotations

import json
import sys
from typing import Any

from assistant import tools

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "personal-booking-assistant", "version": "1.0.0"}


def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _result(request_id: Any, result: dict[str, Any]) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _tool_list() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": schema["name"],
                "description": schema["description"],
                "inputSchema": schema["parameters"],
            }
            for schema in tools.schemas()
        ]
    }


def _tool_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    arguments = params.get("arguments") or {}
    result = tools.run(name, arguments)
    return {
        "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
        "isError": not result.get("ok", True),
    }


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    """Returns the response to send, or None for notifications."""
    method = message.get("method", "")
    request_id = message.get("id")
    params = message.get("params") or {}

    # Notifications have no id and expect no reply.
    if request_id is None:
        return None

    if method == "initialize":
        requested = params.get("protocolVersion", PROTOCOL_VERSION)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": _tool_list()}

    if method == "tools/call":
        return {"jsonrpc": "2.0", "id": request_id, "result": _tool_call(params)}

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue

        try:
            response = handle(message)
        except Exception as exc:  # noqa: BLE001 - a bad tool must not kill the server
            _error(message.get("id"), -32603, f"Internal error: {exc}")
            continue

        if response is not None:
            _send(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
