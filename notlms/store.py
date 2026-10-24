"""User settings and the LMS token, kept in one JSON file on this machine only.

The password is never stored: it is exchanged for a token once, at login.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Config:
    lms_url: str = "https://lms.nust.edu.pk"
    username: str = ""
    token: str = ""
    section: str = ""
    no_sections: bool = False  # True: my courses do not use sections, show everything
    ignore_words: list[str] = field(default_factory=list)  # hide tasks whose name/course contains any
    hidden: dict[str, str] = field(default_factory=dict)  # cmid -> name of tasks the user dismissed
    lookback_days: int = 14
    legacy_tls: bool = True
    remind_hours: list[int] = field(default_factory=lambda: [72, 24, 6, 1])
    poll_minutes: int = 30
    desktop_notifications: bool = True

    @property
    def logged_in(self) -> bool:
        return bool(self.token)

    @property
    def needs_section(self) -> bool:
        return not self.section and not self.no_sections

    def is_ignored(self, name: str, course: str) -> bool:
        text = f"{name} {course}".lower()
        return any(word.lower() in text for word in self.ignore_words)


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.config = Config()
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(Config)}
            self.config = Config(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self.config), fh, indent=2)
            tmp.replace(self.path)

    def forget(self) -> None:
        self.config = Config()
        for path in (self.path,):
            path.unlink(missing_ok=True)
