"""Detect which class section an activity name is meant for.

Combined courses (e.g. "CS-337 ABC") publish one submission link per section
with names like "Lab 6 Submission_sec_C", "Lab 5 Submission Section B",
"Assignment 1 BSCS 14-B" or "Lab-07-[Submission Link] - BSCS14A".
"""

from __future__ import annotations

import re

_PATTERNS = [
    # "sec C", "sec_C", "Section B", "Sec-A"
    re.compile(r"(?<![a-z])sec(?:tion)?[\s_\-]*([a-z])(?![a-z])", re.IGNORECASE),
    # "BSCS-14C", "BSCS 14-B", "BSCS14A"
    re.compile(r"(?<![a-z])bs[a-z]{2}[\s_\-]*\d{2}[\s_\-]*([a-z])(?![a-z])", re.IGNORECASE),
]


def detect_section(name: str) -> str | None:
    for pattern in _PATTERNS:
        match = pattern.search(name)
        if match:
            return match.group(1).upper()
    return None


def is_for_section(name: str, section: str) -> bool:
    """True if the activity is untagged or tagged with the given section."""
    if not section:
        return True
    tagged = detect_section(name)
    return tagged is None or tagged == section.upper()
