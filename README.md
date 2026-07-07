# Pothos

Collect everything Windows knows about an app's failures — in one click.

When an application misbehaves, the evidence is scattered: error and hang events
buried in Event Viewer, crash dumps in `%LOCALAPPDATA%\CrashDumps`, WER reports
under `ProgramData`. Gathering it by hand is slow, repetitive, and easy to get
wrong — exactly the kind of friction QA time disappears into.

Pothos removes it. Enter the executable, pick a time window, choose whether to
compress, and click Collect. You get one folder:

```
myapp_pothos_20260706_141530/
    summary.pdf          the report — every event links to its own file below
    events/
        event_001.txt    one file per error: summary on top, raw XML below
        event_002.txt
    dumps/
        myapp.exe.4242.dmp
        Report.wer
```

Click a row in the PDF and the exact error opens in Notepad. Hand the folder
(or the zip) to a developer and the bug report writes itself.

> Named after the pothos plant — thrives in dark corners and cleans the air.

## Run it

```bash
pip install reportlab
python main.py
```

Windows 10/11. Event collection uses `wevtutil`, which ships with Windows —
no drivers, no pywin32, no admin rights for the Application log.

## Run the tests

```bash
pip install pytest reportlab
pytest
```

27 tests, no Windows required: the Event Log and WER seams are injected, so the
parser is tested against realistic `wevtutil` XML fixtures, dump discovery
against temporary directory layouts, and the full collection run (folder
structure, per-event files, PDF links, zip round-trip) against a fake source.
CI runs the suite on every push.

## Architecture

```
main.py                  tkinter GUI; runs collection off the UI thread
pothos/events.py         pure parsing/filtering of wevtutil XML -> ErrorEvent
pothos/event_source.py   the Windows seam: wevtutil queries (injectable)
pothos/dumps.py          WER/CrashDumps discovery with injectable roots
pothos/collector.py      orchestration: folder layout, event files, zip
pothos/report.py         the PDF summary; rows link to per-event files
```

Design notes: Notepad has no jump-to-line option, so instead of one giant log,
each error is extracted to its own small file and the PDF links to it — the
click lands on exactly the error in question. The core never imports tkinter,
and everything OS-specific sits behind two injectable seams.

## Origin

Rebuilt from scratch after the original (written during hardware/software
validation work) was lost. The second version gained what the first never had:
a full test suite and CI.

---

Built by Liza Sloane — [github.com/Bolero-Dev](https://github.com/Bolero-Dev)
