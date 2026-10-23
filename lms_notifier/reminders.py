"""Decide which tasks deserve a notification on this run, and remember what was sent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .tasks import Task

NEW = "new"
OVERDUE = "overdue"
_RETAIN_SECONDS = 30 * 86400


@dataclass(frozen=True)
class Reminder:
    task: Task
    stage: str  # "new", "overdue", or an hour threshold such as "24"


def current_stage(task: Task, now: float, remind_hours: list[int]) -> str:
    seconds_left = task.due - now
    if seconds_left <= 0:
        return OVERDUE
    crossed = [h for h in remind_hours if seconds_left <= h * 3600]
    return str(min(crossed)) if crossed else NEW


class ReminderState:
    """JSON file mapping task cmid -> stages already notified."""

    def __init__(self, path: Path):
        self.path = path
        self._sent: dict[str, dict] = {}
        if path.is_file():
            self._sent = json.loads(path.read_text(encoding="utf-8")).get("sent", {})

    def was_sent(self, task: Task, stage: str) -> bool:
        return stage in self._sent.get(str(task.cmid), {}).get("stages", [])

    def mark_sent(self, task: Task, stage: str) -> None:
        entry = self._sent.setdefault(str(task.cmid), {"stages": []})
        entry["due"] = task.due
        if stage not in entry["stages"]:
            entry["stages"].append(stage)

    def save(self, now: float) -> None:
        self._sent = {
            cmid: entry
            for cmid, entry in self._sent.items()
            if entry.get("due", 0) > now - _RETAIN_SECONDS
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"sent": self._sent}, indent=2), encoding="utf-8")
        tmp.replace(self.path)


def due_reminders(
    tasks: list[Task], state: ReminderState, now: float, remind_hours: list[int]
) -> list[Reminder]:
    reminders = []
    for task in tasks:
        stage = current_stage(task, now, remind_hours)
        if not state.was_sent(task, stage):
            reminders.append(Reminder(task, stage))
    return reminders
