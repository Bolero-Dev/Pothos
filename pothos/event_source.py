"""
event_source.py

The Windows-facing seam: queries the Event Log via wevtutil (ships with every
Windows install — no pywin32, no drivers, keeping Pothos dependency-light).

Everything above this module works with plain ErrorEvent values, so on
non-Windows machines and in tests this source is replaced with a fake.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

from .events import ErrorEvent, filter_events, parse_wevtutil_xml

# Application failures land in these channels.
DEFAULT_CHANNELS = ("Application", "System")


class WindowsEventSource:
    """Queries Windows Event Log channels through wevtutil."""

    def __init__(self, channels: tuple[str, ...] = DEFAULT_CHANNELS):
        self.channels = channels

    def collect(self, executable: str, hours: float) -> list[ErrorEvent]:
        """Returns error/warning events referencing the executable within
        the last `hours`."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        milliseconds = int(hours * 3600 * 1000)

        all_events: list[ErrorEvent] = []
        for channel in self.channels:
            xml_text = self._query_channel(channel, milliseconds)
            all_events.extend(parse_wevtutil_xml(xml_text))

        return filter_events(all_events, executable, since)

    def _query_channel(self, channel: str, milliseconds: int) -> str:
        """Runs one wevtutil query. Level 1–3 = Critical/Error/Warning."""
        query = (
            f"*[System[(Level=1 or Level=2 or Level=3) and "
            f"TimeCreated[timediff(@SystemTime) <= {milliseconds}]]]"
        )
        command = [
            "wevtutil", "qe", channel,
            f"/q:{query}",
            "/f:xml",
            "/rd:true",   # newest first
            "/e:false",   # no root element; parse_wevtutil_xml wraps it
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""

        if completed.returncode != 0:
            return ""
        return completed.stdout or ""
