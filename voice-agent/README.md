# Personal Voice Assistant

An AI assistant that books tables, makes appointments, keeps your calendar and
**picks up the phone and talks to businesses for you**.

You can use it three different ways. Pick whichever suits you — they all share
the same code underneath:

| # | Way to use it | You need | Best for |
|---|---------------|----------|----------|
| 1 | **Terminal / voice app** you run yourself | An API key | Full control, real phone calls |
| 2 | **Inside Claude** (Claude Desktop or Claude Code) | Nothing extra | Easiest start — Claude *is* the assistant |
| 3 | **Inside ChatGPT** (a Custom GPT) | ChatGPT Plus | Using it from the ChatGPT phone app |

**Never used an API before? Start at [docs/01-beginner-guide.md](docs/01-beginner-guide.md).**
It explains what an API key is, what this costs, and what an "agent" actually is.

---

## 60-second try-out (no API key, no card, no signup)

```bash
cd voice-agent
pip install -r requirements.txt

python -m assistant.cli --provider echo
```

Then type: `book a table at Blue Fin Sushi tomorrow 8pm for 3 people`

`--provider echo` runs a tiny offline stand-in brain so you can watch the
machinery work before spending anything. It only understands a few phrases —
that is the point. Swap in Claude and it understands everything.

## Real version (5 minutes)

```bash
cp .env.example .env
# open .env and paste your key from https://console.anthropic.com
# ANTHROPIC_API_KEY=sk-ant-...

python -m assistant.cli
```

Now try:

```
you  Find a dentist and book me a checkup next Tuesday morning
you  What have I got booked?
you  Remember that I'm vegetarian
you  Book dinner Friday somewhere that works for that
```

Add `--voice` to talk to it out loud instead of typing.

---

## What it can actually do

| Tool | What it does |
|------|--------------|
| `find_business` | Looks up a venue and its phone number |
| `check_availability` | Checks your calendar before booking |
| `create_booking` | Records a booking (restaurant, appointment, hotel, travel) |
| `confirm_booking` / `update_booking` / `cancel_booking` | Manages it afterwards |
| `list_bookings` | "What have I got on?" |
| `place_phone_call` | **Rings a business and holds the conversation** |
| `send_sms` | Texts a confirmation |
| `remember_preference` / `get_preferences` | Learns your diet, usual party size, favourites |
| `get_current_datetime` | So "next Friday" means the right day |

Bookings live in `data/bookings.json` — plain text you can open and read.
Nothing is hidden from you.

---

## How it works (the whole idea in one picture)

```
        you                        the model                    the tools
         |                             |                             |
         |  "book dinner Friday 7pm"   |                             |
         |---------------------------->|                             |
         |                             |  check_availability(...)    |
         |                             |---------------------------->|
         |                             |<----------------------------|
         |                             |   {"free": true}            |
         |                             |                             |
         |                             |  create_booking(...)        |
         |                             |---------------------------->|
         |                             |<----------------------------|
         |  "Booked, Friday 7pm."      |                             |
         |<----------------------------|                             |
```

The model never touches your calendar. It just *asks* for a tool to run, your
code runs it, and the answer goes back. That loop is the entire concept of an
"AI agent", and it's about 40 lines in
[`assistant/agent.py`](assistant/agent.py).

When it phones a restaurant, the same loop runs — the "user" is just a
receptionist and the words arrive as speech instead of typing:

```
   restaurant  --speech-->  Twilio  --text-->  your server  -->  the model
   restaurant  <--speech--  Twilio  <--text--  your server  <--  the model
```

---

## The files

```
voice-agent/
├── assistant/
│   ├── agent.py         THE CORE. The think -> use tool -> think loop.
│   ├── tools.py         Everything it can DO. Add your own here.
│   ├── prompts.py       Its personality + the rules it follows on a call.
│   ├── providers/       Claude / ChatGPT / offline. Swappable brains.
│   ├── store.py         Saves bookings to a JSON file.
│   ├── telephony.py     Twilio: dialling real numbers.
│   ├── voice.py         Your laptop's microphone and speakers.
│   ├── server.py        Handles live phone calls + the REST API.
│   ├── mcp_server.py    Plugs the tools into Claude directly.
│   └── cli.py           The terminal app.
├── docs/                Start here if you're new.
├── openapi/             Schema for a ChatGPT Custom GPT.
└── tests/               66 tests, run them with: pytest
```

---

## Guides

1. **[Beginner guide](docs/01-beginner-guide.md)** — APIs, keys, tokens, costs. No jargon.
2. **[Run it locally](docs/02-run-locally.md)** — install, chat, voice, troubleshooting.
3. **[Make real phone calls](docs/03-phone-calls.md)** — Twilio setup, start to finish.
4. **[Use it inside Claude](docs/04-use-in-claude.md)** — MCP, in 5 minutes.
5. **[Use it inside ChatGPT](docs/05-use-in-chatgpt.md)** — Custom GPT Actions.
6. **[Safety and the law](docs/06-safety-and-law.md)** — read before your first real call.
7. **[Add your own abilities](docs/07-extend-it.md)** — new tools, real calendars, Google Places.

---

## Safety, briefly

- **It asks before it dials.** `REQUIRE_CALL_APPROVAL=true` is the default. The
  agent can only *stage* a call; you say yes before any phone rings.
- **It says it's an AI.** Every call opens by disclosing that. In several places
  that is legally required, and it's the decent thing to do everywhere.
- **It won't invent a confirmation.** A booking stays `requested` until a tool
  result actually says otherwise.

Full detail in [docs/06-safety-and-law.md](docs/06-safety-and-law.md).

## Running the tests

```bash
pytest -q        # 66 tests, no API key or network needed
```
