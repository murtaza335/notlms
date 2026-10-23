"""Notification channels. Each notifier exposes send(title, body)."""

from __future__ import annotations

import json
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Protocol

from ..config import Settings


class Notifier(Protocol):
    name: str

    def send(self, title: str, body: str) -> None: ...


def _http(url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> None:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def _require(settings: Settings, *names: str) -> list[str]:
    values = [settings.get(n) for n in names]
    missing = [n for n, v in zip(names, values) if not v]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    return values


class ConsoleNotifier:
    name = "console"

    def send(self, title: str, body: str) -> None:
        print(f"== {title} ==\n{body}\n")


class NtfyNotifier:
    """Push notifications via ntfy.sh (or a self-hosted ntfy server)."""

    name = "ntfy"

    def __init__(self, settings: Settings):
        (self.topic,) = _require(settings, "NTFY_TOPIC")
        self.server = settings.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

    def send(self, title: str, body: str) -> None:
        payload = json.dumps(
            {"topic": self.topic, "title": title, "message": body, "tags": ["books"], "priority": 4}
        ).encode()
        _http(self.server, payload, {"Content-Type": "application/json"})


class TelegramNotifier:
    name = "telegram"

    def __init__(self, settings: Settings):
        self.token, self.chat_id = _require(settings, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

    def send(self, title: str, body: str) -> None:
        payload = json.dumps(
            {"chat_id": self.chat_id, "text": f"{title}\n\n{body}", "disable_web_page_preview": True}
        ).encode()
        _http(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            payload,
            {"Content-Type": "application/json"},
        )


class EmailNotifier:
    name = "email"

    def __init__(self, settings: Settings):
        self.user, self.password, self.to = _require(settings, "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO")
        self.host = settings.get("SMTP_HOST", "smtp.gmail.com")
        self.port = int(settings.get("SMTP_PORT", "587"))

    def send(self, title: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = self.user
        msg["To"] = self.to
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.send_message(msg)


class WhatsAppNotifier:
    """WhatsApp messages through the free CallMeBot gateway."""

    name = "whatsapp"

    def __init__(self, settings: Settings):
        self.phone, self.apikey = _require(settings, "CALLMEBOT_PHONE", "CALLMEBOT_APIKEY")

    def send(self, title: str, body: str) -> None:
        query = urllib.parse.urlencode({"phone": self.phone, "apikey": self.apikey, "text": f"*{title}*\n\n{body}"})
        _http(f"https://api.callmebot.com/whatsapp.php?{query}")


_REGISTRY = {
    "console": lambda s: ConsoleNotifier(),
    "ntfy": NtfyNotifier,
    "telegram": TelegramNotifier,
    "email": EmailNotifier,
    "whatsapp": WhatsAppNotifier,
}


def build_notifiers(settings: Settings) -> list[Notifier]:
    notifiers = []
    for name in settings.notifiers:
        factory = _REGISTRY.get(name.lower())
        if factory is None:
            raise SystemExit(f"Unknown notifier {name!r}; choose from {', '.join(_REGISTRY)}")
        try:
            notifiers.append(factory(settings))
        except ValueError as exc:
            raise SystemExit(f"Notifier {name!r} is misconfigured: {exc}") from exc
    return notifiers
