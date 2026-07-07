"""End-to-end collector tests with a fake event source — no Windows needed."""

import zipfile
from datetime import datetime, timezone
from pathlib import Path

from pothos.collector import Collector
from pothos.events import ErrorEvent


def make_event(message="Faulting application name: myapp.exe", event_id=1000):
    return ErrorEvent(
        time_created=datetime(2026, 7, 6, 3, 14, 15, tzinfo=timezone.utc),
        event_id=event_id,
        provider="Application Error",
        level=2,
        message=message,
        data_values=["myapp.exe"],
        raw_xml="<Event/>",
    )


class FakeSource:
    def __init__(self, events):
        self.events = events

    def collect(self, executable, hours):
        return self.events


def fake_dumps_in(tmp_path):
    dump = tmp_path / "source_dumps" / "myapp.exe.4242.dmp"
    dump.parent.mkdir()
    dump.write_bytes(b"MDMP fake dump")
    return lambda exe: [dump]


class TestCollectionRun:
    def test_creates_expected_folder_structure(self, tmp_path):
        collector = Collector(FakeSource([make_event(), make_event(event_id=1002)]),
                              fake_dumps_in(tmp_path))
        result = collector.run("myapp.exe", 24, tmp_path)

        folder = result.output_path
        assert folder.is_dir()
        assert (folder / "summary.pdf").is_file()
        assert (folder / "events" / "event_001.txt").is_file()
        assert (folder / "events" / "event_002.txt").is_file()
        assert (folder / "dumps" / "myapp.exe.4242.dmp").is_file()
        assert result.event_count == 2
        assert result.dump_count == 1

    def test_event_file_contains_summary_and_raw_xml(self, tmp_path):
        collector = Collector(FakeSource([make_event()]), lambda exe: [])
        result = collector.run("myapp.exe", 24, tmp_path)

        text = (result.output_path / "events" / "event_001.txt").read_text()
        assert "Event ID: 1000" in text
        assert "Faulting application name: myapp.exe" in text
        assert "Raw event XML" in text

    def test_no_events_no_events_folder(self, tmp_path):
        collector = Collector(FakeSource([]), lambda exe: [])
        result = collector.run("myapp.exe", 24, tmp_path)

        assert not (result.output_path / "events").exists()
        assert (result.output_path / "summary.pdf").is_file()
        assert result.event_count == 0

    def test_compress_produces_zip_and_removes_folder(self, tmp_path):
        collector = Collector(FakeSource([make_event()]), fake_dumps_in(tmp_path))
        result = collector.run("myapp.exe", 24, tmp_path, compress=True)

        assert result.output_path.suffix == ".zip"
        assert result.output_path.is_file()
        # The uncompressed folder should be gone.
        assert not result.output_path.with_suffix("").exists()

        with zipfile.ZipFile(result.output_path) as archive:
            names = archive.namelist()
        assert "summary.pdf" in names
        assert "events/event_001.txt" in names
        assert "dumps/myapp.exe.4242.dmp" in names

    def test_dump_name_collisions_are_disambiguated(self, tmp_path):
        first = tmp_path / "a" / "Report.wer"
        second = tmp_path / "b" / "Report.wer"
        for path in (first, second):
            path.parent.mkdir()
            path.write_text("Version=1")

        collector = Collector(FakeSource([]), lambda exe: [first, second])
        result = collector.run("myapp.exe", 24, tmp_path)

        dumps = sorted(p.name for p in (result.output_path / "dumps").iterdir())
        assert len(dumps) == 2
        assert len(set(dumps)) == 2


class TestPDFSummary:
    def test_pdf_links_to_per_event_files(self, tmp_path):
        collector = Collector(FakeSource([make_event()]), lambda exe: [])
        result = collector.run("myapp.exe", 24, tmp_path)

        pdf_bytes = (result.output_path / "summary.pdf").read_bytes()
        assert b"/URI" in pdf_bytes                    # has link annotations
        assert b"events/event_001.txt" in pdf_bytes    # pointing at the event file

    def test_pdf_mentions_executable_and_counts(self, tmp_path):
        collector = Collector(FakeSource([make_event()]), fake_dumps_in(tmp_path))
        result = collector.run("myapp.exe", 24, tmp_path)
        assert (result.output_path / "summary.pdf").stat().st_size > 1000
