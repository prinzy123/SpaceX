# 4. Use it inside Claude

**This is the easiest way to start. No API key, no billing, no server.**

Claude can pick up new tools through something called **MCP** (Model Context
Protocol). You point Claude at this project once, and from then on Claude itself
can book your tables — you just talk to Claude normally.

The difference from guide 2:

| | Run it yourself (guide 2) | Inside Claude (this guide) |
|-|---------------------------|----------------------------|
| API key | you need one | not needed |
| Who thinks | your code calls the model | Claude, in the app you already use |
| Where you type | your terminal | the Claude app |
| Can place phone calls | yes | yes, once Twilio is set up |

---

## Option A — Claude Desktop

**1. Find your config file**

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Or from the app: **Settings → Developer → Edit Config**.

**2. Add this project** (use the *absolute* path to your `voice-agent` folder):

```json
{
  "mcpServers": {
    "assistant": {
      "command": "python3",
      "args": ["-m", "assistant.mcp_server"],
      "cwd": "/absolute/path/to/voice-agent"
    }
  }
}
```

If you used a virtualenv, point `command` at its python so the packages are
found:

```json
"command": "/absolute/path/to/voice-agent/.venv/bin/python"
```

**3. Restart Claude Desktop completely** (quit, don't just close the window).

**4. Check it worked.** You'll see a tools/plug icon in the message box. Click it
and you should see `create_booking`, `place_phone_call` and the rest.

**5. Use it.**

> "Book me a table for 4 at Blue Fin Sushi on Friday at 7pm"
>
> "What have I got booked next week?"
>
> "Find a dentist near me and call them to book a checkup"

Claude asks your permission the first time it uses each tool.

---

## Option B — Claude Code (the terminal one)

One command, from inside the `voice-agent` folder:

```bash
claude mcp add assistant -- python3 -m assistant.mcp_server
```

Check it:

```bash
claude mcp list
```

Then just talk to Claude Code normally: *"book me a table at Mama Put for Friday
7pm"*.

---

## Option C — the Claude API, in your own code

If you're building your own app rather than using the Claude apps, this is the
minimum working example. This is the "through the API" path you asked about:

```python
import anthropic
from assistant import tools

client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from your environment

# 1. Describe the tools to Claude
tool_schemas = [
    {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
    for t in tools.schemas()
]

messages = [{"role": "user", "content": "Book me a table for 4 at Blue Fin on Friday 7pm"}]

while True:
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        system="You are a helpful booking assistant.",
        tools=tool_schemas,
        messages=messages,
    )

    # 2. Claude replied with text only -> we're done
    if response.stop_reason != "tool_use":
        print(response.content[0].text)
        break

    # 3. Claude wants a tool. Run it and send the result back.
    messages.append({"role": "assistant", "content": response.content})
    results = []
    for block in response.content:
        if block.type == "tool_use":
            output = tools.run(block.name, block.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(output),
            })
    messages.append({"role": "user", "content": results})
```

That loop is the whole thing. `assistant/agent.py` is this, plus a step limit,
plus support for swapping in GPT.

---

## Which should I use?

- **Just want it working today** → Option A.
- **Already live in the terminal** → Option B.
- **Building your own product** → Option C.

Note that Options A and B mean *Claude* does the thinking — so the phone-call
personality in `prompts.py` isn't used for chat, only for live calls. If you want
the exact assistant behaviour defined in this project, run it yourself (guide 2).

---

## Troubleshooting

**Tools don't appear**
Restart Claude Desktop fully. Check the JSON is valid (a trailing comma breaks
it silently). Check `cwd` is an absolute path.

**"spawn python3 ENOENT"**
Claude can't find python. Use the full path: `/usr/bin/python3`, or your
virtualenv's python.

**Tools appear but every call errors**
Test the server by hand from the `voice-agent` folder:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 -m assistant.mcp_server
```

You should get a JSON list of tools. If you get an import error, your `cwd` or
python path is wrong.

**Where did my bookings go?**
`voice-agent/data/bookings.json`. Same file whichever way you use the assistant.

---

Next: **[5. Use it inside ChatGPT →](05-use-in-chatgpt.md)**
