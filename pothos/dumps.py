"""
dumps.py

Crash dump discovery. Windows Error Reporting scatters artifacts across a few
well-known locations; this module knows where to look and which files belong
to the executable under investigation.

The search roots are injectable, so the matching logic is fully testable with
temporary directories on any platform.
"""

from __future__ import annotations

import os
from pathlib import Path


def default_dump_roots() -> list[Path]:
    """The standard WER locations on a Windows machine."""
    roots = []

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        roots.append(Path(local_appdata) / "CrashDumps")

    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    wer = Path(program_data) / "Microsoft" / "Windows" / "WER"
    roots.append(wer / "ReportArchive")
    roots.append(wer / "ReportQueue")

    return roots


def find_crash_artifacts(
    executable: str,
    roots: list[Path] | None = None,
) -> list[Path]:
    """Finds dump files and WER report folders belonging to the executable.

    Matching is by the executable's stem, case-insensitively:
    - CrashDumps:      myapp.exe.12345.dmp
    - WER reports:     AppCrash_myapp.exe_<hash>/  (folder of Report.wer + dumps)
    """
    stem = Path(executable).stem.lower()
    if not stem:
        return []

    found: list[Path] = []
    for root in roots if roots is not None else default_dump_roots():
        if not root.is_dir():
            continue

        for entry in sorted(root.iterdir()):
            name = entry.name.lower()
            if stem not in name:
                continue

            if entry.is_file() and entry.suffix.lower() == ".dmp":
                found.append(entry)
            elif entry.is_dir():
                # A WER report folder: take its files (Report.wer, .dmp, etc.)
                found.extend(
                    child for child in sorted(entry.iterdir()) if child.is_file()
                )

    return found
