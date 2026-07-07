"""
main.py

Pothos — collect everything Windows knows about an app's failures, in one click.

Enter the executable name, pick a time window, choose whether to compress,
and Collect. The run happens off the UI thread; results land in a folder
containing a PDF summary, per-error text files, and any crash dumps.

Run:  python main.py   (Windows; requires reportlab: pip install reportlab)
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from pothos.collector import Collector
from pothos.dumps import find_crash_artifacts
from pothos.event_source import WindowsEventSource

TIME_WINDOWS = {
    "Last hour": 1,
    "Last 6 hours": 6,
    "Last 24 hours": 24,
    "Last 3 days": 72,
    "Last 7 days": 168,
}


class PothosWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Pothos — Diagnostic Collector")
        root.geometry("560x360")
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)

        # Executable
        ttk.Label(frame, text="Application executable (e.g. myapp.exe):").pack(anchor="w")
        self.exe_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.exe_var, width=50).pack(anchor="w", pady=(2, 10))

        # Time window
        ttk.Label(frame, text="Time window:").pack(anchor="w")
        self.window_var = tk.StringVar(value="Last 24 hours")
        ttk.Combobox(
            frame, textvariable=self.window_var,
            values=list(TIME_WINDOWS), state="readonly", width=20,
        ).pack(anchor="w", pady=(2, 10))

        # Destination
        dest_row = ttk.Frame(frame)
        dest_row.pack(fill="x", pady=(0, 10))
        ttk.Label(dest_row, text="Save to:").pack(side="left")
        self.dest_var = tk.StringVar(value=str(Path.home() / "Desktop"))
        ttk.Entry(dest_row, textvariable=self.dest_var, width=38).pack(side="left", padx=6)
        ttk.Button(dest_row, text="Browse…", command=self._pick_destination).pack(side="left")

        # Compression — decided up front, exactly as the workflow intends.
        self.compress_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Compress results into a .zip", variable=self.compress_var
        ).pack(anchor="w", pady=(0, 12))

        self.collect_button = ttk.Button(frame, text="Collect", command=self._start)
        self.collect_button.pack(anchor="w")

        self.status = tk.Text(frame, height=6, width=64, state="disabled", relief="solid", borderwidth=1)
        self.status.pack(fill="x", pady=(12, 0))

    # MARK: actions

    def _pick_destination(self):
        chosen = filedialog.askdirectory(initialdir=self.dest_var.get())
        if chosen:
            self.dest_var.set(chosen)

    def _start(self):
        executable = self.exe_var.get().strip()
        if not executable:
            self._log("Enter an executable name first.")
            return

        hours = TIME_WINDOWS[self.window_var.get()]
        destination = Path(self.dest_var.get())
        compress = self.compress_var.get()

        self.collect_button.state(["disabled"])
        self._log(f"Collecting events and crash artifacts for {executable} "
                  f"({self.window_var.get().lower()})…")

        thread = threading.Thread(
            target=self._collect, args=(executable, hours, destination, compress),
            daemon=True,
        )
        thread.start()

    def _collect(self, executable: str, hours: float, destination: Path, compress: bool):
        try:
            collector = Collector(WindowsEventSource(), find_crash_artifacts)
            result = collector.run(executable, hours, destination, compress=compress)
            self._log(
                f"Done: {result.event_count} event(s), {result.dump_count} crash "
                f"artifact(s).\nSaved to: {result.output_path}"
            )
        except Exception as exc:  # surfaced to the user, never swallowed
            self._log(f"Collection failed: {exc}")
        finally:
            self.root.after(0, lambda: self.collect_button.state(["!disabled"]))

    def _log(self, message: str):
        def append():
            self.status.configure(state="normal")
            self.status.insert("end", message + "\n")
            self.status.see("end")
            self.status.configure(state="disabled")
        self.root.after(0, append)


def main():
    root = tk.Tk()
    PothosWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
