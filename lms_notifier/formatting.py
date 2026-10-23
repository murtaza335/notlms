"""Render reminders as human-readable text."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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


def format_task_line(task: Task, now: float, tz: ZoneInfo) -> str:
    due = datetime.fromtimestamp(task.due, tz).strftime("%a %d %b %H:%M")
    left = task.due - now
    when = f"OVERDUE by {humanize_delta(left)}" if left <= 0 else f"{humanize_delta(left)} left"
    return f"[{when}] {short_course(task.course)} - {task.name}\n  Due {due} - {task.url}"


def format_digest(reminders: list[Reminder], now: float, tz: ZoneInfo) -> tuple[str, str]:
    """Return (title, body) for one notification covering all reminders."""
    overdue = sum(1 for r in reminders if r.stage == OVERDUE)
    count = len(reminders)
    title = f"LMS: {count} pending task{'s' if count != 1 else ''}"
    if overdue:
        title += f" ({overdue} overdue)"
    body = "\n\n".join(format_task_line(r.task, now, tz) for r in reminders)
    return title, body
