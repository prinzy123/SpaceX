# 5. Use it inside ChatGPT

Two ways: a **Custom GPT** (chat to it in the ChatGPT app), or the **OpenAI API**
(build your own thing).

---

## Option A — a Custom GPT

Requires **ChatGPT Plus**. A Custom GPT can call your server, so you get your
assistant inside the ChatGPT phone app.

### 1. Put your server on the internet

```bash
# terminal 1
uvicorn assistant.server:app --port 8000
# terminal 2
ngrok http 8000
```

Set a password in `.env` first — this URL is public:

```bash
SERVER_API_KEY=some-long-random-string-you-invent
```

Restart the server after changing `.env`.

### 2. Create the GPT

1. <https://chatgpt.com> → your name → **My GPTs** → **Create a GPT**
2. **Configure** tab
3. **Name:** `My Booking Assistant`
4. **Instructions:**

```
You are the user's personal booking assistant.

For anything about bookings, reservations, appointments, or phoning a business,
use the talkToAssistant action and pass the user's request through almost
verbatim. It handles the details itself.

Use listBookings when they ask what they have on.

approveCall makes a real phone ring. Only use it after the user has clearly said
yes to that specific call, and always tell them who is about to be called first.

Never claim a booking is confirmed unless the action's response says confirmed.
```

### 3. Add the Action

**Actions → Create new action → Schema**

Paste the contents of [`openapi/gpt-actions.yaml`](../openapi/gpt-actions.yaml),
then change one line near the top to your ngrok URL:

```yaml
servers:
  - url: https://a1b2c3.ngrok-free.app
```

**Authentication → API Key**
- Auth Type: **API Key**
- Custom header name: `X-API-Key`
- API Key: the same `SERVER_API_KEY` from your `.env`

### 4. Test it

In the preview pane: *"Book me a table for 4 at Blue Fin Sushi on Friday at 7pm"*

You should see the action fire, and a booking land in `data/bookings.json`.

### Notes

- Free ngrok URLs change on restart. When it changes, update the `servers:` URL
  in the GPT too, or actions fail with a connection error.
- For permanent use, deploy the server somewhere real (Railway, Render, Fly.io,
  a VPS) and use that fixed URL instead.

---

## Option B — the OpenAI API in your own code

Same idea as the Claude example, different shape. This project already supports
it — set `LLM_PROVIDER=openai` in `.env` and everything works — but here's the
raw loop so you can see it:

```python
import json
from openai import OpenAI
from assistant import tools

client = OpenAI()   # reads OPENAI_API_KEY from your environment

tool_schemas = [
    {"type": "function",
     "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
    for t in tools.schemas()
]

messages = [
    {"role": "system", "content": "You are a helpful booking assistant."},
    {"role": "user", "content": "Book me a table for 4 at Blue Fin on Friday 7pm"},
]

while True:
    response = client.chat.completions.create(
        model="gpt-4o", messages=messages, tools=tool_schemas
    )
    reply = response.choices[0].message

    if not reply.tool_calls:
        print(reply.content)
        break

    messages.append(reply)
    for call in reply.tool_calls:
        output = tools.run(call.function.name, json.loads(call.function.arguments))
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(output),
        })
```

Spot the difference from the Claude version:

| | Claude | OpenAI |
|-|--------|--------|
| System prompt | separate `system=` argument | first message in the list |
| Tool schema key | `input_schema` | `parameters`, wrapped in `function` |
| Tool arguments | already a dict | a JSON **string** you must parse |
| Sending results back | a `user` message of `tool_result` blocks | messages with `role: "tool"` |

Those four differences are exactly what `assistant/providers/` hides for you, so
the rest of the project never has to care which one you're using.

---

## Which is better for this?

Honestly, either. Use whichever key you already have. Two practical notes:

- For **live phone calls**, prefer a fast model. A two-second pause feels like a
  dropped call to whoever answered.
- **Claude Desktop's MCP route (guide 4) needs no API key at all**, which is the
  cheapest possible way to try this.

---

Next: **[6. Safety and the law →](06-safety-and-law.md)**
