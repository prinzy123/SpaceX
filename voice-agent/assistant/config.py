"""All settings live here, read once from the .env file.

Nothing else in the project reads os.environ directly, so this file is the
single place to look when something is "not configured".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional dependency: the project still runs without it
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - only hit when python-dotenv is absent
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # --- the brain ---
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "claude").lower())
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-5"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "1024")))

    # --- the phone ---
    twilio_account_sid: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    twilio_auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    twilio_from_number: str = field(default_factory=lambda: os.getenv("TWILIO_FROM_NUMBER", ""))
    public_base_url: str = field(
        default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    )

    # --- you ---
    owner_name: str = field(default_factory=lambda: os.getenv("OWNER_NAME", "my client"))
    owner_phone: str = field(default_factory=lambda: os.getenv("OWNER_PHONE", ""))
    owner_email: str = field(default_factory=lambda: os.getenv("OWNER_EMAIL", ""))
    timezone: str = field(default_factory=lambda: os.getenv("OWNER_TIMEZONE", "UTC"))

    # --- safety ---
    require_call_approval: bool = field(
        default_factory=lambda: _flag("REQUIRE_CALL_APPROVAL", True)
    )
    server_api_key: str = field(default_factory=lambda: os.getenv("SERVER_API_KEY", ""))

    # --- storage ---
    data_dir: Path = DATA_DIR

    @property
    def telephony_ready(self) -> bool:
        """True when we have everything needed to dial a real phone number."""
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_from_number
            and self.public_base_url
        )

    def missing_telephony(self) -> list[str]:
        names = {
            "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
            "TWILIO_FROM_NUMBER": self.twilio_from_number,
            "PUBLIC_BASE_URL": self.public_base_url,
        }
        return [key for key, value in names.items() if not value]


settings = Settings()
