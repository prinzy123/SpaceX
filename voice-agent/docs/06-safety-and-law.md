# 6. Safety and the law

Short guide, worth the two minutes. An AI that phones strangers is different
from an AI that writes emails — there's a real person on the other end who
didn't sign up for anything.

---

## The three rules built into this project

**1. It tells people it's an AI.**

Every outbound call opens with:

> *"Hi, quick heads up — I'm an AI assistant calling on behalf of Ada Obi."*

This lives in `AI_DISCLOSURE` in `assistant/prompts.py`. **Don't remove it.**
Several jurisdictions require disclosure of a synthetic voice — California's
B.O.T. Act, and rules from the US FCC treating AI-generated voices as artificial
under the TCPA, among others. Beyond legality: people are entitled to know.

**2. It won't dial without you saying yes.**

`REQUIRE_CALL_APPROVAL=true` is the default. The model can only *stage* a call;
you see the number and the objective and approve it. Turn this off only for
numbers you fully control.

**3. It won't claim a booking is confirmed when it isn't.**

Bookings stay `requested` until a tool result says otherwise. The phone agent has
to report `RESULT: confirmed` before the status changes. A "helpful" lie about a
table that doesn't exist is worse than no assistant.

---

## Things to check before your first real call

- **Recording.** This project doesn't record audio, but Twilio *transcribes*
  speech, and transcripts are saved in `data/calls.json`. Many places (two-party
  consent US states, the UK, most of the EU) have rules about recording calls. If
  you enable Twilio's recording features, announce it.
- **Who you're calling.** Never point this at emergency services, government
  lines, hotlines, or anyone who hasn't chosen to do business by phone. The
  system prompt forbids it; don't work around that.
- **Volume.** One assistant booking your dinner is fine. The same code dialling
  hundreds of numbers is robocalling, which is illegal in most countries and will
  get your Twilio account terminated regardless.
- **Personal data.** The prompt restricts what it shares to your name and phone
  number. Don't extend it to card numbers or your home address — a phone agent
  can be socially engineered, and it can't tell a scam from a receptionist.

---

## What this project deliberately does not do

- **No payments.** It never gives out card details or agrees to charges.
- **No voice cloning.** It uses an obviously synthetic voice. Sounding like a
  specific real person is a different thing entirely, legally and ethically.
- **No blocked-number spoofing.** Calls come from your real Twilio number.
- **No pretending to be human.** If someone asks "am I talking to a robot?", the
  honest answer is in the prompt.

---

## If someone asks it to stop

The prompt tells it to apologise, say goodbye and hang up if the other person
objects or says they don't take AI calls. Respect that — a business that doesn't
want AI calls is entitled not to get them. Call them yourself.

---

## Protecting your own accounts

- **Never commit `.env`.** It's in `.gitignore`. Check `git status` before you
  push anything.
- **Set a spend limit** in the Anthropic/OpenAI console on day one.
- **Set a `SERVER_API_KEY`** before exposing your server via ngrok — otherwise
  anyone who guesses the URL can spend your credit and dial numbers with your
  phone account.
- **Rotate a leaked key immediately.** Revoke it in the console; it takes seconds.

---

## Common sense summary

Use it to save yourself phone calls you'd have made anyway. Don't use it to make
calls the other person wouldn't want. If you'd feel awkward telling the person
you sent an AI, that's your answer.

---

Next: **[7. Add your own abilities →](07-extend-it.md)**
