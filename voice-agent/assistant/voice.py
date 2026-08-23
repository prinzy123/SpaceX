"""Talking to your assistant out loud on your own computer.

Two halves:
  * listen()  -- microphone -> text  (speech recognition)
  * speak()   -- text -> speakers    (text to speech)

Both are optional. If the audio libraries are missing, the assistant still works
perfectly by typing -- you just get a clear message instead of a crash.

Install on Ubuntu/Debian:  sudo apt install portaudio19-dev espeak
Then:                      pip install -r requirements-voice.txt
"""

from __future__ import annotations

import logging

log = logging.getLogger("assistant.voice")

_engine = None


class VoiceUnavailable(RuntimeError):
    """Raised when the audio libraries or hardware are not there."""


def speak(text: str) -> None:
    """Say something through the speakers. Falls back to printing."""
    global _engine
    if not text.strip():
        return
    try:
        import pyttsx3

        if _engine is None:
            _engine = pyttsx3.init()
            _engine.setProperty("rate", 175)
        _engine.say(text)
        _engine.runAndWait()
    except Exception as exc:  # noqa: BLE001 - never let audio break the assistant
        log.debug("text-to-speech unavailable: %s", exc)
        print(f"[assistant would say] {text}")


def listen(timeout: int = 8, phrase_limit: int = 20) -> str:
    """Record one sentence from the microphone and return it as text."""
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise VoiceUnavailable(
            "Microphone support is not installed. Run:\n"
            "  pip install -r requirements-voice.txt\n"
            "(on Ubuntu first: sudo apt install portaudio19-dev espeak)"
        ) from exc

    recogniser = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recogniser.adjust_for_ambient_noise(source, duration=0.4)
            print("listening...")
            audio = recogniser.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    except OSError as exc:
        raise VoiceUnavailable(f"No usable microphone found: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - sr raises WaitTimeoutError etc.
        raise VoiceUnavailable(f"Could not record audio: {exc}") from exc

    try:
        # Google's free web endpoint -- no key needed, fine for personal use.
        return recogniser.recognize_google(audio)
    except Exception as exc:  # noqa: BLE001 - UnknownValueError / RequestError
        log.debug("transcription failed: %s", exc)
        return ""


def available() -> bool:
    try:
        import pyttsx3  # noqa: F401
        import speech_recognition  # noqa: F401
    except ImportError:
        return False
    return True
