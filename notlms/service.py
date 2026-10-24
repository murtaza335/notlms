"""Background sync: fetch pending tasks, fire desktop reminders, keep a snapshot for the UI."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import desktop
from .formatting import course_label, format_digest, format_due, time_left
from .moodle import MoodleClient, MoodleError
from .reminders import ReminderState, due_reminders
from .store import ConfigStore
from .tasks import Task, TaskCollector

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    tasks: list[Task] = field(default_factory=list)
    synced_at: float = 0.0
    error: str = ""
    syncing: bool = False
    notify_error: str = ""


class Service:
    def __init__(self, store: ConfigStore, state_path: Path):
        self.store = store
        self.state_path = state_path
        self.snapshot = Snapshot()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="notlms-sync", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def sync_soon(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self.store.config.logged_in:
                self.sync()
            self._wake.wait(timeout=max(1, self.store.config.poll_minutes) * 60)
            self._wake.clear()

    def sync(self) -> None:
        cfg = self.store.config
        with self._lock:
            self.snapshot.syncing = True
            try:
                now = time.time()
                client = MoodleClient(cfg.lms_url, legacy_tls=cfg.legacy_tls)
                client.token = cfg.token
                tasks = TaskCollector(client, section=cfg.section, lookback_days=cfg.lookback_days).collect(now)
                self.snapshot.tasks = tasks
                self.snapshot.synced_at = now
                self.snapshot.error = ""
                self._remind(tasks, now)
            except MoodleError as exc:
                if "invalidtoken" in str(exc):
                    self.snapshot.error = "Your LMS session expired. Please log in again."
                else:
                    self.snapshot.error = str(exc)
                log.warning("Sync failed: %s", exc)
            except OSError as exc:
                self.snapshot.error = f"Could not reach the LMS: {exc}"
                log.warning("Sync failed: %s", exc)
            finally:
                self.snapshot.syncing = False

    def _remind(self, tasks: list[Task], now: float) -> None:
        cfg = self.store.config
        state = ReminderState(self.state_path)
        reminders = due_reminders(tasks, state, now, sorted(cfg.remind_hours, reverse=True))
        if not reminders or not cfg.desktop_notifications:
            return
        title, body = format_digest(reminders, now)
        try:
            desktop.notify(title, body)
        except RuntimeError as exc:
            self.snapshot.notify_error = str(exc)
            log.warning("%s", exc)
            return
        self.snapshot.notify_error = ""
        for reminder in reminders:
            state.mark_sent(reminder.task, reminder.stage)
        state.save(now)

    def status(self) -> dict:
        cfg = self.store.config
        now = time.time()
        snap = self.snapshot
        return {
            "logged_in": cfg.logged_in,
            "username": cfg.username,
            "lms_url": cfg.lms_url,
            "settings": {
                "section": cfg.section,
                "remind_hours": cfg.remind_hours,
                "poll_minutes": cfg.poll_minutes,
                "desktop_notifications": cfg.desktop_notifications,
            },
            "synced_at": snap.synced_at,
            "syncing": snap.syncing,
            "error": snap.error,
            "notify_error": snap.notify_error,
            "tasks": [
                {
                    "name": t.name,
                    "course": course_label(t),
                    "module": t.module,
                    "due": t.due,
                    "due_text": format_due(t),
                    "left_text": time_left(t, now),
                    "overdue": t.due <= now,
                    "url": t.url,
                }
                for t in snap.tasks
            ],
        }
