"""Render tasks and reminders as human-readable text (times in the local zone)."""

from __future__ import annotations

from datetime import datetime

from .reminders import OVERDUE, Reminder
from .tasks import Task


def humanize_delta(seconds: float) -> str:
    seconds = abs(int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def short_course(course: str) -> str:
    """'CS-337-F'26 ABC 2K24-BSCS-14' -> 'CS-337'."""
    head = course.split()[0] if course else course
    parts = head.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else head


def time_left(task: Task, now: float) -> str:
    left = task.due - now
    return f"overdue by {humanize_delta(left)}" if left <= 0 else f"{humanize_delta(left)} left"


def format_due(task: Task) -> str:
    return datetime.fromtimestamp(task.due).astimezone().strftime("%a %d %b %H:%M")


def format_digest(reminders: list[Reminder], now: float) -> tuple[str, str]:
    """Return (title, body) for one notification covering all reminders."""
    overdue = sum(1 for r in reminders if r.stage == OVERDUE)
    count = len(reminders)
    title = f"notlms: {count} pending task{'s' if count != 1 else ''}"
    if overdue:
        title += f" ({overdue} overdue)"
    lines = [f"{short_course(r.task.course)} {r.task.name} ({time_left(r.task, now)})" for r in reminders]
    return title, "\n".join(lines)
