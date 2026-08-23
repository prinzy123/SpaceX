# 1. Beginner guide — what all of this actually means

You said you're new to this. Nothing below assumes you've done it before.

---

## What is an API?

An API is a way for one program to ask another program to do something.

You already use APIs without noticing. When a weather app shows the forecast, it
didn't calculate the weather — it sent a message to a weather company's computer
saying "forecast for Lagos please", and got an answer back.

**The Claude API is exactly that, but the thing you're asking for is thinking.**
You send some text, you get intelligent text back.

```
your code  --"book a table Friday"-->  Anthropic's computers
your code  <--"which restaurant?"-----  Anthropic's computers
```

That's it. That's the whole thing.

---

## What is an API key?

A password that identifies you, so the company knows who to bill.

It looks like `sk-ant-api03-x7Kd9...`. Three rules:

1. **It is a password.** Anyone who has it can spend your money.
2. **Never put it in your code.** That's why it goes in a `.env` file, which
   `.gitignore` stops from ever being uploaded to GitHub.
3. **If you leak it, delete it.** Go to the console, revoke it, make a new one.
   Takes 10 seconds. People leak keys constantly; it's recoverable.

### Getting one

**Claude (recommended for this project):**
1. Go to <https://console.anthropic.com>
2. Sign up → **API Keys** → **Create Key**
3. Copy it *now* — you can't see it again afterwards
4. Add some credit (Billing → $5 is plenty to start)

**ChatGPT/GPT (the alternative):**
1. Go to <https://platform.openai.com/api-keys>
2. Same steps.

> ⚠️ A **ChatGPT Plus subscription is not an API key.** They're separate products
> with separate bills. Lots of beginners get caught by this.

---

## What does it cost?

You pay per *token*. A token is roughly ¾ of a word — "unbelievable" is about
3 tokens, "cat" is 1.

You pay for what you send (input) and what comes back (output). Output costs
more, because that's the part the model has to generate.

**Realistically, for this assistant:**

| What you do | Roughly costs |
|-------------|---------------|
| One chat message ("book me a table") | a fraction of a US cent |
| A full booking conversation with tools | under 1 cent |
| A 3-minute phone call to a restaurant | a few cents of model + ~5¢ Twilio |
| Using it every day for a month | a couple of dollars |

**$5 of credit will last a beginner a long time.** The expensive part of this
project is the phone number ($1/month), not the intelligence.

Two things that protect you:
- `MAX_STEPS = 8` in `agent.py` stops a confused model looping and burning credit.
- Set a hard spend limit in the console. Do this on day one.

For current per-model prices, check the provider's pricing page — they change,
and I'd rather you read the real number than trust a number in a README.

---

## What is a "model"? Which one do I pick?

The model is the specific brain. Bigger ones are smarter and cost more.

This project defaults to **Claude Sonnet** — the middle option — because for
booking a table you want good instruction-following and low latency, not the
world's deepest reasoning. Change it in `.env`:

```bash
CLAUDE_MODEL=claude-sonnet-5     # balanced, the default here
# CLAUDE_MODEL=claude-opus-5     # smarter, slower, pricier
# CLAUDE_MODEL=claude-haiku-4-5-20251001  # fastest and cheapest
```

For phone calls, **speed matters more than raw intelligence** — a two-second
silence feels broken to whoever answered. Sonnet or Haiku are the right call.

---

## What is an "agent"? What is a "tool"?

A plain chatbot can only produce words. It cannot look at your calendar, and if
you ask it to, it will make something up.

An **agent** is a chatbot that's been handed a list of buttons it may press. You
describe each button in words:

> `create_booking` — records a booking. Needs: business_name, kind, starts_at.

Now the model can reply with *"press create_booking with these values"* instead
of guessing. Your code presses the button, and hands the result back.

**A tool is just a normal function plus a description of it.** Here's a real one
from this project, complete:

```python
@tool("List the owner's upcoming bookings.", _obj({"limit": _INT}))
def list_bookings(limit: int = 20) -> dict:
    return {"ok": True, "bookings": store.upcoming(limit)}
```

That's a whole tool. The decorator registers the description; the function does
the work. The model can now answer "what have I got on Friday?" truthfully.

The magic word people use for this is **function calling** or **tool use**. It's
the same thing.

---

## So what is this project, in one sentence?

A list of tools about booking things, plus the loop that lets a model use them,
plus a phone line so it can use them while talking to a human.

---

## The three ways to run it, and which to choose

**"I just want to try it"** → [Use it inside Claude](04-use-in-claude.md).
No API key, no billing. Claude Desktop launches this project's tools and Claude
itself does the thinking. 5 minutes.

**"I want it to actually phone people"** → [Run it locally](02-run-locally.md),
then [set up Twilio](03-phone-calls.md). This is the real thing.

**"I want it on my phone"** → [Custom GPT](05-use-in-chatgpt.md) if you have
ChatGPT Plus, or point the Claude mobile app at your deployed server.

---

## Words you'll keep meeting

| Word | Means |
|------|-------|
| **API** | One program asking another program for something |
| **API key** | Your password/billing identity for that |
| **Token** | ~¾ of a word; the unit you're billed in |
| **Model** | The specific brain (Sonnet, Opus, GPT-4o...) |
| **Prompt** | The instructions you give the model |
| **System prompt** | Standing instructions — its personality and rules |
| **Tool / function calling** | Letting the model trigger your code |
| **Agent** | A model in a loop, using tools until the job's done |
| **MCP** | The standard that lets Claude pick up tools like these |
| **Webhook** | A URL someone else's server calls when something happens |
| **TwiML** | The XML you send Twilio to say "say this, then listen" |
| **ngrok** | Gives your laptop a public URL so Twilio can reach it |
| **STT / TTS** | Speech→text (listening) / text→speech (talking) |

---

Next: **[2. Run it locally →](02-run-locally.md)**
