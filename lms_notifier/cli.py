"""Command-line entry point.

    lms-notifier list         show every pending task (no notifications)
    lms-notifier run          notify about tasks that crossed a reminder stage
    lms-notifier test-notify  send a test message through each channel
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings, load_dotenv
from .formatting import format_digest, format_task_line
from .moodle import MoodleClient
from .notifiers import build_notifiers
from .reminders import ReminderState, due_reminders
from .tasks import TaskCollector

log = logging.getLogger("lms_notifier")


def _collect(settings: Settings, now: float):
    client = MoodleClient(settings.lms_url, legacy_tls=settings.legacy_tls)
    client.login(settings.username, settings.password)
    collector = TaskCollector(client, section=settings.section, lookback_days=settings.lookback_days)
    return collector.collect(now)


def cmd_list(settings: Settings) -> int:
    now = time.time()
    tz = ZoneInfo(settings.timezone)
    tasks = _collect(settings, now)
    if not tasks:
        print("Nothing pending.")
    for task in tasks:
        print(format_task_line(task, now, tz))
    return 0


def cmd_run(settings: Settings, dry_run: bool) -> int:
    now = time.time()
    tz = ZoneInfo(settings.timezone)
    notifiers = build_notifiers(settings)
    tasks = _collect(settings, now)
    state = ReminderState(settings.state_file)
    reminders = due_reminders(tasks, state, now, settings.remind_hours)
    log.info("%d pending tasks, %d need a reminder", len(tasks), len(reminders))
    if not reminders:
        return 0

    title, body = format_digest(reminders, now, tz)
    if dry_run:
        print(f"[dry run] would send via {', '.join(n.name for n in notifiers)}:\n{title}\n{body}")
        return 0

    delivered = False
    for notifier in notifiers:
        try:
            notifier.send(title, body)
            delivered = True
        except Exception:
            log.exception("Sending via %s failed", notifier.name)
    if not delivered:
        return 1
    for reminder in reminders:
        state.mark_sent(reminder.task, reminder.stage)
    state.save(now)
    return 0


def cmd_test_notify(settings: Settings) -> int:
    failures = 0
    for notifier in build_notifiers(settings):
        try:
            notifier.send("LMS notifier test", "If you can read this, the channel works.")
            print(f"ok: {notifier.name}")
        except Exception as exc:
            failures += 1
            print(f"FAILED: {notifier.name}: {exc}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lms-notifier", description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show pending tasks")
    run = sub.add_parser("run", help="send reminders that are due")
    run.add_argument("--dry-run", action="store_true", help="print instead of sending")
    sub.add_parser("test-notify", help="send a test message on every channel")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv(args.env_file)
    settings = Settings.from_env()

    if args.command == "list":
        return cmd_list(settings)
    if args.command == "run":
        return cmd_run(settings, args.dry_run)
    return cmd_test_notify(settings)


if __name__ == "__main__":
    sys.exit(main())
