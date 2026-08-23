# 2. Run it on your own machine

## Step 1 — get the code and install

```bash
cd voice-agent
python3 -m venv .venv           # a private box for this project's packages
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

That's everything for text chat, bookings and **real phone calls**.

### Optional: your laptop's microphone and speakers

Only needed for `--voice`. It's a separate file because these packages compile
against system libraries, and if one fails to build, pip abandons the *whole*
install — so keeping them apart stops a missing audio library from leaving you
with no assistant at all.

Install the system libraries first:

- **Ubuntu/Debian:** `sudo apt install portaudio19-dev espeak`
- **macOS:** `brew install portaudio`
- **Windows:** `pip install pipwin && pipwin install pyaudio`

Then:

```bash
pip install -r requirements-voice.txt
```

If this fails, don't worry about it — everything except `--voice` still works,
including phoning restaurants.

## Step 2 — try it with no key at all

```bash
python -m assistant.cli --provider echo
```

```
you  book a table at Blue Fin Sushi tomorrow 8pm for 3 people
  -> create_booking(business_name='Blue Fin Sushi', party_size=3, ...)
  <- create_booking: ok
```

Those dim `->` and `<-` lines are the model using a tool. Watching them is the
fastest way to understand what an agent is doing.

## Step 3 — add a real brain

```bash
cp .env.example .env
```

Open `.env` and set two lines:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-real-key
LLM_PROVIDER=claude
```

While you're there, fill in your name and timezone — the assistant introduces
itself with your name when it calls people:

```bash
OWNER_NAME=Ada Obi
OWNER_TIMEZONE=Africa/Lagos
OWNER_PHONE=+2348012345678
```

Then:

```bash
python -m assistant.cli
```

## Step 4 — talk to it

```bash
pip install -r requirements-voice.txt    # if you haven't already, see step 1
python -m assistant.cli --voice
```

Speak; it replies out loud. It uses your computer's microphone and speakers, and
free Google speech recognition. (Phone calls are a separate thing — see
[guide 3](03-phone-calls.md).)

---

## Everything you can type

| Command | Does |
|---------|------|
| `/bookings` | Your upcoming bookings |
| `/calls` | Staged and completed calls, with transcripts |
| `/approve call_xxx` | Dial a staged call |
| `/help` | Reminder of all this |
| `/quit` | Exit |

One-shot mode, handy for scripts and keyboard shortcuts:

```bash
python -m assistant.cli "what have I got booked this week?"
```

Force a different brain for one run:

```bash
python -m assistant.cli --provider openai
python -m assistant.cli --provider echo
```

---

## Things worth trying

```
Find a dentist and book me a checkup next Tuesday morning
Remember that I'm vegetarian and I usually book for 2
Book dinner Friday somewhere that works for that
Move my Friday booking to 8pm
What have I got on next week?
Cancel the dentist, something came up
```

Notice it asks *one* question at a time when something's missing, checks your
calendar before booking, and applies preferences you told it once.

---

## When something goes wrong

**`ANTHROPIC_API_KEY is not set`**
Your `.env` isn't being read. Check you're in the `voice-agent/` folder, the file
is named exactly `.env` (not `.env.txt`), and there are no quotes or spaces
around the key.

**`RuntimeError: The anthropic package is missing`**
`pip install -r requirements.txt` — and check your virtualenv is active
(`which python` should point inside `.venv`).

**`401 Unauthorized` / `authentication_error`**
The key is wrong, revoked, or belongs to a different provider than
`LLM_PROVIDER` says. A `sk-ant-` key with `LLM_PROVIDER=openai` fails like this.

**`429` / `rate_limit_error` / `credit balance is too low`**
Add credit in the console. New accounts sometimes start at zero.

**"I got stuck repeating myself"**
The safety cap in `agent.py` kicked in after 8 tool calls. Usually means a tool
kept failing. Look at the dim `<-` lines to see which one.

**It made up a booking that doesn't exist**
Check `data/bookings.json`. If the booking is there, it's real — the assistant
only writes through tools. If it isn't, you're on `--provider echo`, which is a
canned demo, not a real model.

**Microphone doesn't work**
`python -c "import assistant.voice as v; print(v.available())"` → `False` means
the audio packages are missing. See step 1. The assistant works fine by typing
in the meantime.

---

Next: **[3. Make real phone calls →](03-phone-calls.md)**
