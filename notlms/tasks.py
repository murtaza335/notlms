"""Collect pending (unsubmitted) activities from Moodle."""

from __future__ import annotations

import logging
import time
import urllib.parse
from dataclasses import dataclass

from .moodle import MoodleClient, MoodleError
from .sections import is_for_section

log = logging.getLogger(__name__)

_EVENT_PAGE_SIZE = 50


@dataclass(frozen=True)
class Task:
    cmid: int
    name: str
    course: str
    module: str
    due: int  # unix timestamp
    cutoff: int  # unix timestamp, 0 = no hard cutoff
    url: str

    def is_open(self, now: float) -> bool:
        return not self.cutoff or now < self.cutoff


def _cmid_from_url(url: str) -> int | None:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    try:
        return int(query["id"][0])
    except (KeyError, ValueError, IndexError):
        return None


def _clean_name(name: str) -> str:
    for suffix in (" is due", " closes", " should be completed"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def fetch_action_events(client: MoodleClient, since: int) -> list[dict]:
    """All calendar events that still require an action from the user."""
    events: list[dict] = []
    after_id = 0
    while True:
        page = client.call(
            "core_calendar_get_action_events_by_timesort",
            timesortfrom=since,
            limitnum=_EVENT_PAGE_SIZE,
            aftereventid=after_id or None,
        )["events"]
        events.extend(page)
        if len(page) < _EVENT_PAGE_SIZE:
            return events
        after_id = page[-1]["id"]


class TaskCollector:
    def __init__(self, client: MoodleClient, *, section: str = "", lookback_days: int = 14):
        self.client = client
        self.section = section
        self.lookback_days = lookback_days
        self._assignments: dict[int, dict] = {}
        self._quizzes: dict[int, dict] = {}

    def collect(self, now: float | None = None) -> list[Task]:
        now = time.time() if now is None else now
        events = fetch_action_events(self.client, int(now) - self.lookback_days * 86400)
        relevant = [e for e in events if is_for_section(e["name"], self.section)]
        log.info("%d action events, %d for section %r", len(events), len(relevant), self.section or "*")

        course_ids = sorted({e["course"]["id"] for e in relevant})
        self._load_activity_metadata(course_ids)

        tasks: list[Task] = []
        for event in relevant:
            task = self._to_task(event)
            if task is None or not task.is_open(now):
                continue
            if self._is_done(task):
                log.debug("Already completed: %s", task.name)
                continue
            tasks.append(task)
        return sorted(tasks, key=lambda t: t.due)

    def _load_activity_metadata(self, course_ids: list[int]) -> None:
        if not course_ids:
            return
        result = self.client.call("mod_assign_get_assignments", courseids=course_ids)
        self._assignments = {a["cmid"]: a for c in result["courses"] for a in c["assignments"]}
        try:
            result = self.client.call("mod_quiz_get_quizzes_by_courses", courseids=course_ids)
            self._quizzes = {q["coursemodule"]: q for q in result["quizzes"]}
        except MoodleError as exc:
            log.warning("Could not load quizzes: %s", exc)

    def _to_task(self, event: dict) -> Task | None:
        cmid = _cmid_from_url(event.get("url", ""))
        if cmid is None:
            return None
        cutoff = 0
        if event["modulename"] == "assign" and cmid in self._assignments:
            cutoff = self._assignments[cmid].get("cutoffdate") or 0
        return Task(
            cmid=cmid,
            name=_clean_name(event["name"]),
            course=event["course"].get("shortname") or event["course"].get("fullname", ""),
            module=event["modulename"],
            due=event["timesort"],
            cutoff=cutoff,
            url=event["url"],
        )

    def _is_done(self, task: Task) -> bool:
        """Double-check completion; action events usually exclude finished work already."""
        try:
            if task.module == "assign" and task.cmid in self._assignments:
                status = self.client.call(
                    "mod_assign_get_submission_status",
                    assignid=self._assignments[task.cmid]["id"],
                )
                submission = (status.get("lastattempt") or {}).get("submission") or {}
                return submission.get("status") == "submitted"
            if task.module == "quiz" and task.cmid in self._quizzes:
                attempts = self.client.call(
                    "mod_quiz_get_user_attempts",
                    quizid=self._quizzes[task.cmid]["id"],
                    status="finished",
                )
                return bool(attempts.get("attempts"))
        except MoodleError as exc:
            log.warning("Status check failed for %s: %s", task.name, exc)
        return False
