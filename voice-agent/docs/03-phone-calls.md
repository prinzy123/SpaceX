# 3. Making real phone calls

This is the part people find magical: your assistant rings a restaurant, talks
to whoever picks up, and books your table.

**Read [6. Safety and the law](06-safety-and-law.md) before your first real
call.** It's short. Some of it is not optional.

---

## How a call actually works

Twilio is a phone company you can program. You rent a number, and when your code
says "dial this", Twilio dials — then asks *your* server what to say next.

```
1. your code -> Twilio          "call +234803..."
2. Twilio    -> the restaurant   *ring ring*
3. they pick up
4. Twilio    -> your server      POST /voice/outbound   "they answered, what now?"
5. your server -> Twilio         <Say>Hi, I'm an AI assistant...</Say><Gather/>
6. they speak; Twilio transcribes it
7. Twilio    -> your server      POST /voice/turn  SpeechResult="sure, what time?"
8. your server asks the model, replies with more <Say> + <Gather>
9. ... repeat until the agent says goodbye ...
```

Steps 4–8 are why you need a *public* URL: Twilio's computers must be able to
reach your laptop.

---

## Setup, start to finish

### 1. Twilio account and number

1. Sign up at <https://twilio.com/try-twilio> (free trial includes credit)
2. Console → **Phone Numbers → Buy a number**
3. Pick one with **Voice** capability (~$1/month)
4. From the Console dashboard, copy your **Account SID** and **Auth Token**

> On a trial account you can only call numbers you've verified in the console.
> Verify your own mobile and test on that first. It's a good habit anyway.

### 2. Give your laptop a public address

```bash
# in a second terminal, leave it running
ngrok http 8000
```

Copy the `https://` URL it prints, e.g. `https://a1b2c3.ngrok-free.app`.

> Free ngrok URLs change every restart. When it changes, update
> `PUBLIC_BASE_URL` in `.env` and restart the server — otherwise Twilio calls a
> dead address and your calls end in silence.

### 3. Fill in `.env`

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+15550001111
PUBLIC_BASE_URL=https://a1b2c3.ngrok-free.app
OWNER_NAME=Ada Obi
REQUIRE_CALL_APPROVAL=true
```

### 4. Start the server

```bash
uvicorn assistant.server:app --port 8000
```

Check it: <http://localhost:8000/health> should show
`"telephony_ready": true`. If it's `false`, the response lists exactly which
variable is missing.

### 5. Make the call

In another terminal:

```bash
python -m assistant.cli
```

```
you  Call Mama Put Kitchen and book a table for 4 this Friday at 7pm

  -> find_business(query='Mama Put')
  -> place_phone_call(to_number='+2348030000001', objective='Book a table for 4...')

CALL WAITING FOR YOUR APPROVAL
  to      : Mama Put Kitchen (+2348030000001)
  purpose : Book a table for 4 on Friday 19:00 under Ada. If full, take 18:30-20:30.
  id      : call_7f3a91b2c4
Dial it now? [y/N]
```

Press `y` and the phone rings.

Afterwards, `/calls` shows the full transcript, and if the venue confirmed, the
booking flips to `confirmed` with its reference number automatically.

---

## Receiving calls (call your own assistant)

You can also ring your assistant and talk to it hands-free while driving.

In the Twilio console → your number → **Voice Configuration** →
*A call comes in* → **Webhook** → `https://your-url.ngrok-free.app/voice/incoming`
→ HTTP POST.

Now call your Twilio number: *"What have I got booked tomorrow?"*

---

## Writing a good objective

The agent on the call **cannot ask you anything mid-conversation**. Everything it
might need must be in the objective. Compare:

❌ `"Book a table"`
✅ `"Book a table for 4 on Friday 19:00 under Ada Obi. If 19:00 is unavailable,
accept anything between 18:30 and 20:30. Ask whether they have vegetarian
options. Get a reference number if they give one."`

The second one survives a receptionist saying "we're full at seven".

---

## Costs

| | Roughly |
|-|---------|
| Phone number | ~$1/month |
| Outbound call | ~1–3¢/minute (varies hugely by country) |
| Speech recognition | ~2¢/minute |
| The model | under a cent for a short call |

A 3-minute booking call lands around 10–15¢.

---

## Troubleshooting

**Call connects, then silence, then hangs up**
Twilio can't reach your server. Check ngrok is running, `PUBLIC_BASE_URL`
matches its *current* URL exactly (https, no trailing slash), and the server is
up. Twilio Console → **Monitor → Logs → Errors** tells you precisely what it hit.

**`403 Invalid Twilio signature`**
`PUBLIC_BASE_URL` doesn't match the URL Twilio actually called. Usually a stale
ngrok URL or `http` vs `https`.

**"The number is unverified"**
Trial accounts can only call verified numbers. Verify it, or upgrade.

**It mishears everything**
Speech recognition struggles with strong background noise and some accents. Keep
the agent's questions short and closed ("Is seven pm available?" beats "What
times do you have?"). After two unintelligible replies it hangs up politely
rather than looping and billing you.

**It hung up too early**
The model emitted `[[END_CALL]]` prematurely. Tighten the objective, or edit
`PHONE_SYSTEM` in `assistant/prompts.py`.

**It talks too long / rambles**
Same file. The prompt already says short spoken sentences; make it stricter, or
switch to a faster model — latency matters more than eloquence on a call.

---

Next: **[4. Use it inside Claude →](04-use-in-claude.md)**
