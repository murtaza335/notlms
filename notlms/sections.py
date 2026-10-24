"""Detect which class section an activity name is meant for.

Combined courses (e.g. "CS-337 ABC") publish one submission link per section
with names like "Lab 6 Submission_sec_C", "Lab 5 Submission Section B",
"Assignment 1 BSCS 14-B", "Lab-07-[Submission Link] - BSCS14A" or
"Quiz 3 (Sec A & B)".
"""

from __future__ import annotations

import re

_SEP = r"\s*(?:,|/|&|\+|and)\s*"
_PATTERNS = [
    # "sec C", "sec_C", "Section B", "Sec-A", "Sections A, B", "Section A and B", "Sec A/B"
    re.compile(rf"(?<![a-z])sec(?:tion)?s?[\s_\-:.]*([a-z](?:{_SEP}[a-z](?![a-z]))*)(?![a-z])", re.IGNORECASE),
    # "BSCS-14C", "BSCS 14-B", "BEE13A", "BESE-12 D", "MS-CS 22A"
    re.compile(
        r"(?<![a-z])(?:bs|be|bba|bit|mba|msc|ms|phd)[a-z]{0,3}[\s_\-]*\d{2}[\s_\-]*([a-z])(?![a-z0-9])",
        re.IGNORECASE,
    ),
    # a lone letter in brackets: "(B)", "[C]"
    re.compile(r"[(\[]\s*([a-z])\s*[)\]]", re.IGNORECASE),
]
_LETTER = re.compile(r"(?<![a-z])[a-z](?![a-z])", re.IGNORECASE)


def detect_sections(name: str) -> set[str]:
    """Every section letter the name is tagged with (empty if untagged)."""
    found: set[str] = set()
    for pattern in _PATTERNS:
        for match in pattern.finditer(name):
            found.update(letter.upper() for letter in _LETTER.findall(match.group(1)))
    return found


def detect_section(name: str) -> str | None:
    """First section letter in the name, or None."""
    found = sorted(detect_sections(name))
    return found[0] if found else None


def parse_section(text: str) -> str:
    """Normalise what a user typed ('b', 'Section B', 'BSCS-14B') to a single letter.

    Raises ValueError when no single section can be determined.
    """
    text = text.strip()
    if re.fullmatch(r"[A-Za-z]", text):
        return text.upper()
    found = detect_sections(text)
    if len(found) == 1:
        return next(iter(found))
    raise ValueError("Enter just your section letter, for example B.")


def is_for_section(name: str, section: str) -> bool:
    """True if the activity is untagged or tagged for the given section (among others).

    An empty section disables filtering.
    """
    if not section:
        return True
    tagged = detect_sections(name)
    return not tagged or section.upper() in tagged
