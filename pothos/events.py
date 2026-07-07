"""
events.py

Parsing and filtering of Windows Event Log records.

This module is pure: it takes wevtutil XML output as text and returns typed
ErrorEvent values. Nothing here touches the OS, which is what makes the whole
pipeline testable on any platform — the Windows-specific querying lives in
event_source.py.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

# The Windows Event schema namespace used by wevtutil XML output.
NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

# Event IDs that matter when hunting application failures.
APPLICATION_ERROR = 1000   # Application Error (faulting module, exception code)
APPLICATION_HANG = 1002    # Application Hang
WER_REPORT = 1001          # Windows Error Reporting (often references the dump)

LEVEL_NAMES = {1: "Critical", 2: "Error", 3: "Warning", 4: "Information"}


@dataclass
class ErrorEvent:
    """One event log record, reduced to what a QA engineer needs."""
    time_created: datetime
    event_id: int
    provider: str
    level: int
    message: str
    data_values: list[str] = field(default_factory=list)
    raw_xml: str = ""

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, f"Level {self.level}")

    def mentions(self, executable: str) -> bool:
        """True if this event references the executable anywhere.

        Faulting-application events carry the exe path in EventData; hangs and
        WER reports sometimes only mention it in the rendered message. Check
        both, case-insensitively, so nothing slips through on capitalization.
        """
        needle = executable.lower()
        if needle in self.message.lower():
            return True
        return any(needle in value.lower() for value in self.data_values)


def parse_wevtutil_xml(xml_text: str) -> list[ErrorEvent]:
    """Parses wevtutil output into ErrorEvent values.

    wevtutil emits a sequence of <Event> elements with no document root, so
    the text is wrapped before parsing. Records that fail to parse are skipped
    rather than sinking the whole collection — one malformed event should not
    cost the user the other two hundred.
    """
    wrapped = f"<Events>{xml_text}</Events>"
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        return []

    events = []
    for element in root.findall("e:Event", NS):
        parsed = _parse_event(element)
        if parsed is not None:
            events.append(parsed)
    return events


def _parse_event(element: ET.Element) -> ErrorEvent | None:
    system = element.find("e:System", NS)
    if system is None:
        return None

    time_el = system.find("e:TimeCreated", NS)
    id_el = system.find("e:EventID", NS)
    provider_el = system.find("e:Provider", NS)
    level_el = system.find("e:Level", NS)

    if time_el is None or id_el is None:
        return None

    time_created = _parse_system_time(time_el.get("SystemTime", ""))
    if time_created is None:
        return None

    data_values = [
        data.text
        for data in element.findall("e:EventData/e:Data", NS)
        if data.text
    ]

    message_el = element.find("e:RenderingInfo/e:Message", NS)
    if message_el is not None and message_el.text:
        message = message_el.text.strip()
    else:
        # No rendered message (wevtutil without /rd:true, or missing provider
        # metadata) — fall back to the raw data values, which still contain
        # the faulting application, module, and exception code.
        message = "\n".join(data_values)

    return ErrorEvent(
        time_created=time_created,
        event_id=int(id_el.text or 0),
        provider=(provider_el.get("Name", "Unknown") if provider_el is not None else "Unknown"),
        level=int(level_el.text or 0) if level_el is not None else 0,
        message=message,
        data_values=data_values,
        raw_xml=ET.tostring(element, encoding="unicode"),
    )


def _parse_system_time(value: str) -> datetime | None:
    """Parses Event Log SystemTime (ISO-8601, up to 7 fractional digits, Z)."""
    if not value:
        return None
    # Python's fromisoformat handles at most 6 fractional digits.
    value = re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def filter_events(
    events: list[ErrorEvent],
    executable: str,
    since: datetime,
    max_level: int = 3,
) -> list[ErrorEvent]:
    """Keeps events that reference the executable, in range, at or above
    the requested severity (lower level number = more severe).

    Sorted newest first: the failure you're chasing is usually the latest one.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    matching = [
        event for event in events
        if event.time_created >= since
        and 0 < event.level <= max_level
        and event.mentions(executable)
    ]
    return sorted(matching, key=lambda event: event.time_created, reverse=True)
