"""Talk to your assistant from the terminal.

    python -m assistant.cli                 # type at it
    python -m assistant.cli --voice         # talk to it with your microphone
    python -m assistant.cli --provider echo # no API key needed, offline demo

In-chat commands:  /bookings   /calls   /approve <call_id>   /help   /quit
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from assistant import telephony
from assistant.agent import Agent
from assistant.config import settings
from assistant.providers import get_provider
from assistant.store import store

DIM, BOLD, GREEN, YELLOW, RED, RESET = (
    "\033[2m", "\033[1m", "\033[32m", "\033[33m", "\033[31m", "\033[0m",
)


def _show_event(kind: str, payload: dict[str, Any]) -> None:
    if kind == "tool_start":
        args = ", ".join(f"{k}={v!r}" for k, v in payload["arguments"].items())
        print(f"{DIM}  -> {payload['name']}({args[:110]}){RESET}")
    elif kind == "tool_end":
        result = payload["result"]
        mark = f"{GREEN}ok{RESET}" if result.get("ok") else f"{RED}failed: {result.get('error','')}{RESET}"
        print(f"{DIM}  <- {payload['name']}: {mark}{RESET}")


def _pending_calls() -> list[dict[str, Any]]:
    return [c for c in store.calls.all() if c["status"] == "awaiting_approval"]


def _handle_approvals(speak_fn: Any) -> None:
    """After each turn, ask the human to approve any call the agent staged."""
    for call in _pending_calls():
        print(
            f"\n{YELLOW}{BOLD}CALL WAITING FOR YOUR APPROVAL{RESET}\n"
            f"  to      : {call['business_name']} ({call['to_number']})\n"
            f"  purpose : {call['objective']}\n"
            f"  id      : {call['id']}"
        )
        answer = input(f"{BOLD}Dial it now? [y/N] {RESET}").strip().lower()
        if answer in {"y", "yes"}:
            result = telephony.approve_and_dial(call["id"])
            note = result.get("message") or f"Dialing... (sid {result.get('sid', 'n/a')})"
            print(f"{GREEN}{note}{RESET}")
            speak_fn("Calling them now.")
        else:
            store.calls.update(call["id"], status="declined")
            print(f"{DIM}Cancelled. Nothing was dialled.{RESET}")


def _print_bookings() -> None:
    rows = store.upcoming()
    if not rows:
        print(f"{DIM}No bookings yet.{RESET}")
        return
    for row in rows:
        colour = GREEN if row["status"] == "confirmed" else YELLOW
        print(
            f"  {row['starts_at']:<18} {row['business_name']:<22} "
            f"party {row['party_size']:<3} {colour}{row['status']}{RESET}  {DIM}{row['id']}{RESET}"
        )


def _print_calls() -> None:
    rows = store.calls.all()[-10:]
    if not rows:
        print(f"{DIM}No calls yet.{RESET}")
        return
    for row in rows:
        print(f"  {row['id']}  {row['business_name']:<22} {row['status']:<18} {DIM}{row['outcome']}{RESET}")


HELP = f"""{BOLD}Commands{RESET}
  /bookings          show your upcoming bookings
  /calls             show staged and completed calls
  /approve <id>      dial a staged call
  /help              this list
  /quit              exit

{BOLD}Try saying{RESET}
  "Book me a table for 4 at Blue Fin Sushi on Friday at 7pm"
  "Find a dentist and call them for a checkup next week"
  "What have I got booked?"
  "Remember that I'm vegetarian"
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Your personal booking assistant.")
    parser.add_argument("--voice", action="store_true", help="use microphone and speakers")
    parser.add_argument("--provider", default=None, help="claude | openai | echo")
    parser.add_argument("message", nargs="*", help="say one thing and exit")
    args = parser.parse_args(argv)

    try:
        provider = get_provider(args.provider)
    except (RuntimeError, ValueError) as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    speak_fn: Any = lambda text: None
    if args.voice:
        from assistant import voice

        speak_fn = voice.speak

    agent = Agent(provider=provider, on_event=_show_event)

    def one_turn(text: str) -> None:
        turn = agent.send(text)
        print(f"\n{BOLD}assistant{RESET} {turn.reply}\n")
        speak_fn(turn.reply)
        _handle_approvals(speak_fn)

    # One-shot mode:  python -m assistant.cli "book a table tonight"
    if args.message:
        one_turn(" ".join(args.message))
        return 0

    print(
        f"{BOLD}Personal assistant ready{RESET} {DIM}(brain: {provider.name}, "
        f"calling: {'on' if settings.telephony_ready else 'dry-run'}){RESET}\n"
        f"{DIM}Type /help for commands, /quit to leave.{RESET}\n"
    )

    while True:
        try:
            if args.voice:
                from assistant import voice

                try:
                    user_input = voice.listen()
                except voice.VoiceUnavailable as exc:
                    print(f"{RED}{exc}{RESET}\nFalling back to typing.")
                    args.voice = False
                    continue
                if not user_input:
                    print(f"{DIM}(didn't catch that){RESET}")
                    continue
                print(f"{BOLD}you{RESET} {user_input}")
            else:
                user_input = input(f"{BOLD}you{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not user_input:
            continue

        lowered = user_input.lower()
        if lowered in {"/quit", "/exit", "quit", "exit"}:
            print("Bye.")
            return 0
        if lowered == "/help":
            print(HELP)
            continue
        if lowered == "/bookings":
            _print_bookings()
            continue
        if lowered == "/calls":
            _print_calls()
            continue
        if lowered.startswith("/approve"):
            parts = user_input.split()
            if len(parts) < 2:
                print(f"{RED}Usage: /approve <call_id>{RESET}")
                continue
            print(telephony.approve_and_dial(parts[1]))
            continue

        one_turn(user_input)


if __name__ == "__main__":
    sys.exit(main())
