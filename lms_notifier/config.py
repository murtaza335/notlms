"""Settings loaded from environment variables (optionally via a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Populate os.environ from a KEY=VALUE file without overriding real env vars."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str = "") -> list[str]:
    return [part.strip() for part in _env(name, default).split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    lms_url: str
    username: str
    password: str
    section: str
    lookback_days: int
    legacy_tls: bool
    remind_hours: list[int]
    timezone: str
    state_file: Path
    notifiers: list[str]
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        missing = [n for n in ("LMS_USERNAME", "LMS_PASSWORD") if not _env(n)]
        if missing:
            raise SystemExit(f"Missing required settings: {', '.join(missing)} (see .env.example)")
        return cls(
            lms_url=_env("LMS_URL", "https://lms.nust.edu.pk").rstrip("/"),
            username=_env("LMS_USERNAME"),
            password=os.environ["LMS_PASSWORD"],
            section=_env("LMS_SECTION").upper(),
            lookback_days=int(_env("LMS_LOOKBACK_DAYS", "14")),
            legacy_tls=_env_bool("LMS_LEGACY_TLS", True),
            remind_hours=sorted({int(h) for h in _env_list("REMIND_HOURS", "72,24,6,1")}, reverse=True),
            timezone=_env("TIMEZONE", "Asia/Karachi"),
            state_file=Path(_env("STATE_FILE", ".state/state.json")),
            notifiers=_env_list("NOTIFIERS", "console"),
            extra=dict(os.environ),
        )

    def get(self, name: str, default: str = "") -> str:
        """Look up a channel-specific setting (e.g. NTFY_TOPIC)."""
        return self.extra.get(name, default).strip()
