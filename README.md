# Pothos

Everything Windows knows about an app's failures, collected in one click.

When an application misbehaves, the evidence is scattered all over the place:
error and hang events buried in Event Viewer, crash dumps in
`%LOCALAPPDATA%\CrashDumps`, WER reports under `ProgramData`. Collecting it by
hand is slow, repetitive, and easy to get wrong — the kind of chore QA time
quietly disappears into. I got tired of doing it by hand, so I made the
computer do it.

Enter the executable, pick a time window, click Collect. You get one folder:

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
(or the zip) to a developer and the bug report basically writes itself.

> Named after the pothos plant — it thrives in dark corners and cleans the
> air. So does this.

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

27 tests, and none of them need Windows: the Event Log and WER lookups sit
behind injectable seams, so the parser runs against realistic `wevtutil` XML
fixtures, dump discovery runs against temporary directory layouts, and the full
collection run (folder structure, per-event files, PDF links, zip round-trip)
runs against a fake source. CI runs the suite on every push.

## Architecture

```
main.py                  tkinter GUI; runs collection off the UI thread
pothos/events.py         pure parsing/filtering of wevtutil XML -> ErrorEvent
pothos/event_source.py   the Windows seam: wevtutil queries (injectable)
pothos/dumps.py          WER/CrashDumps discovery with injectable roots
pothos/collector.py      orchestration: folder layout, event files, zip
pothos/report.py         the PDF summary; rows link to per-event files
```

One design choice worth explaining: Notepad has no jump-to-line, so instead of
one giant log, every error gets its own small file and the PDF links straight
to it. The click lands on exactly the error in question — no scrolling, no
searching. The core never imports tkinter, and everything OS-specific sits
behind two seams you can swap out.

## The origin story

I wrote the first version of Pothos during hardware/software validation work,
and then I lost it. This is the rebuild — and the rebuild got what the
original never had: a full test suite and CI. Losing the code hurt; finding
out the design was worth rebuilding from memory didn't.

---

Built by Liza Sloane — [github.com/Bolero-Dev](https://github.com/Bolero-Dev)
