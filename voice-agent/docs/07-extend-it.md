# 7. Add your own abilities

The assistant can do exactly what's in `assistant/tools.py`. Adding to that list
is the main way you make this yours.

---

## Add a tool in 3 minutes

Say you want it to check the weather before booking an outdoor table. Open
`assistant/tools.py` and add:

```python
@tool(
    "Check the weather forecast for a date, to advise on outdoor bookings.",
    _obj(
        {
            "city": _STR,
            "date": {**_STR, "description": "ISO date, e.g. 2026-09-04"},
        },
        ["city", "date"],
    ),
)
def check_weather(city: str, date: str) -> dict:
    # replace with a real API call when you're ready
    return {"ok": True, "city": city, "date": date, "forecast": "sunny, 28C"}
```

That's it. It now works in the CLI, on phone calls, in Claude via MCP, and in
your Custom GPT — no other file changes.

### The rules that matter

1. **The description is the user interface.** The model chooses tools by reading
   it. "Check the weather" is vague; "Check the weather forecast for a date, to
   advise on outdoor bookings" tells it *when* to reach for this.
2. **Always return a dict with `ok`.** `{"ok": False, "error": "..."}` on failure.
   The model reads the error and recovers; an exception just kills the turn.
3. **Describe every argument.** Especially date formats. Say
   `"ISO datetime, e.g. 2026-09-04T19:00"` and you'll get that back.
4. **Keep results small.** Every character is a token you pay for. Return the 5
   nearest restaurants, not 500.

Then test it:

```bash
python -c "from assistant import tools; print(tools.run('check_weather', {'city':'Lagos','date':'2026-09-04'}))"
```

---

## Swap the fake address book for real business search

`find_business` reads `data/businesses.json`. For real lookups, use Google Places.
Add `import os` and `import requests` at the top of `tools.py` first
(`pip install requests`), then replace the function:

```python

@tool(
    "Search for a real business and get its phone number and address.",
    _obj({"query": _STR, "near": _STR}, ["query"]),
)
def find_business(query: str, near: str = "") -> dict:
    response = requests.get(
        "https://maps.googleapis.com/maps/api/place/textsearch/json",
        params={"query": f"{query} {near}".strip(), "key": os.environ["GOOGLE_PLACES_KEY"]},
        timeout=10,
    )
    results = response.json().get("results", [])[:5]
    return {
        "ok": bool(results),
        "results": [
            {"name": r["name"], "address": r.get("formatted_address", ""), "place_id": r["place_id"]}
            for r in results
        ],
    }
```

(Phone numbers need a second Place Details call — that's the API's design, not
an oversight here.)

---

## Use your real calendar instead of a JSON file

Right now `check_availability` reads `data/bookings.json`. To use Google
Calendar, replace the body of `check_availability` and `create_booking` with
calls to the Calendar API. Everything else — the prompts, the phone agent, the
MCP server — keeps working, because they only know the tool *names*.

That's the payoff of keeping tools thin: swapping the storage doesn't touch the
agent.

---

## Ideas worth building

| Idea | Tools you'd add |
|------|-----------------|
| Ring you when a table frees up | `watch_availability`, plus a scheduled job |
| Handle flights and hotels | `search_flights`, `hold_reservation` |
| Reschedule everything when a meeting moves | `find_affected_bookings`, `propose_new_times` |
| Group dinners | `poll_attendees` over SMS, then book the winner |
| Follow-up reminders | `schedule_reminder` + a cron job hitting `/assistant/message` |

---

## Changing its personality

`assistant/prompts.py` holds two prompts:

- `ASSISTANT_SYSTEM` — how it talks to you. Make it terser, funnier, or more
  formal here.
- `PHONE_SYSTEM` — how it behaves on a live call. Edit carefully and test on
  your own phone first. Keep the AI disclosure line (see
  [guide 6](06-safety-and-law.md)).

---

## Running the tests

```bash
pytest -q                        # all 66, no API key needed
pytest tests/test_server.py -v   # just the phone-call webhooks
```

If you add a tool, add a test. The pattern is in `tests/test_tools.py` — they
use a temporary data folder, so they never touch your real bookings.

The most valuable tests here are the phone ones, because a bug in `/voice/turn`
means dead air on a real call with a real person.

---

Back to the **[README](../README.md)**.
