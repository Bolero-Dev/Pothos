"""
collector.py

Orchestrates a collection run: query events, find crash artifacts, write the
output folder, build the PDF summary, optionally compress.

Output layout:
    <app>_<timestamp>/
        summary.pdf
        events/event_001.txt ...    (one file per error — PDF links open these)
        dumps/...                   (copied crash dumps and WER reports)

The event source and dump finder are injected, so this whole pipeline runs
under test with fakes on any platform.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from .events import ErrorEvent


class EventCollecting(Protocol):
    def collect(self, executable: str, hours: float) -> list[ErrorEvent]: ...


DumpFinder = Callable[[str], list[Path]]


@dataclass
class CollectionSummary:
    """Everything the report needs to describe one collection run."""
    executable: str
    hours: float
    collected_at: datetime
    # (event, path relative to the output folder) pairs
    event_files: list[tuple[ErrorEvent, Path]] = field(default_factory=list)
    # paths relative to the output folder
    dump_files: list[Path] = field(default_factory=list)


@dataclass
class CollectionResult:
    output_path: Path        # the folder, or the .zip if compressed
    event_count: int
    dump_count: int


class Collector:
    def __init__(self, event_source: EventCollecting, dump_finder: DumpFinder):
        self.event_source = event_source
        self.dump_finder = dump_finder

    def run(
        self,
        executable: str,
        hours: float,
        destination: Path,
        compress: bool = False,
    ) -> CollectionResult:
        """Executes one collection run and returns where the results landed."""
        collected_at = datetime.now()
        stamp = collected_at.strftime("%Y%m%d_%H%M%S")
        folder = destination / f"{Path(executable).stem}_pothos_{stamp}"
        folder.mkdir(parents=True, exist_ok=False)

        summary = CollectionSummary(
            executable=executable, hours=hours, collected_at=collected_at
        )

        self._write_event_files(executable, hours, folder, summary)
        self._copy_dumps(executable, folder, summary)

        # Import here so the core stays importable without reportlab
        # (e.g. running only the parsing tests).
        from .report import build_pdf
        build_pdf(summary, folder / "summary.pdf")

        if compress:
            archive = shutil.make_archive(str(folder), "zip", root_dir=folder)
            shutil.rmtree(folder)
            output = Path(archive)
        else:
            output = folder

        return CollectionResult(
            output_path=output,
            event_count=len(summary.event_files),
            dump_count=len(summary.dump_files),
        )

    # MARK: internals

    def _write_event_files(
        self,
        executable: str,
        hours: float,
        folder: Path,
        summary: CollectionSummary,
    ) -> None:
        events = self.event_source.collect(executable, hours)
        if not events:
            return

        events_dir = folder / "events"
        events_dir.mkdir()

        for index, event in enumerate(events, start=1):
            relative = Path("events") / f"event_{index:03d}.txt"
            (folder / relative).write_text(
                _render_event_text(event), encoding="utf-8"
            )
            summary.event_files.append((event, relative))

    def _copy_dumps(
        self, executable: str, folder: Path, summary: CollectionSummary
    ) -> None:
        artifacts = self.dump_finder(executable)
        if not artifacts:
            return

        dumps_dir = folder / "dumps"
        dumps_dir.mkdir()

        seen_names: set[str] = set()
        for artifact in artifacts:
            # Flatten WER folder structures; disambiguate name collisions.
            name = artifact.name
            if name in seen_names:
                name = f"{artifact.parent.name}_{name}"
            seen_names.add(name)

            try:
                shutil.copy2(artifact, dumps_dir / name)
            except OSError:
                continue  # locked or vanished mid-copy; skip, don't sink the run
            summary.dump_files.append(Path("dumps") / name)


def _render_event_text(event: ErrorEvent) -> str:
    """The per-event text file: human summary on top, raw XML below."""
    lines = [
        f"Time:     {event.time_created.isoformat()}",
        f"Event ID: {event.event_id}",
        f"Level:    {event.level_name}",
        f"Provider: {event.provider}",
        "",
        "Message:",
        event.message or "(no rendered message)",
        "",
        "-" * 70,
        "Raw event XML:",
        event.raw_xml,
    ]
    return "\n".join(lines)
