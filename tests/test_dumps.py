"""Tests for crash artifact discovery using temporary directory fixtures."""

from pothos.dumps import find_crash_artifacts


def make_wer_layout(tmp_path):
    """Builds a realistic WER directory layout for myapp.exe and a stranger."""
    crash_dumps = tmp_path / "CrashDumps"
    crash_dumps.mkdir()
    (crash_dumps / "myapp.exe.4242.dmp").write_bytes(b"MDMP")
    (crash_dumps / "other.exe.1.dmp").write_bytes(b"MDMP")
    (crash_dumps / "notes.txt").write_text("not a dump")

    archive = tmp_path / "ReportArchive"
    archive.mkdir()
    report = archive / "AppCrash_myapp.exe_c0ffee123"
    report.mkdir()
    (report / "Report.wer").write_text("Version=1")
    (report / "memory.hdmp").write_bytes(b"MDMP")
    (archive / "AppCrash_other.exe_dead").mkdir()

    return [crash_dumps, archive]


class TestDiscovery:
    def test_finds_dump_files_for_the_executable(self, tmp_path):
        roots = make_wer_layout(tmp_path)
        found = find_crash_artifacts("myapp.exe", roots)
        names = [p.name for p in found]
        assert "myapp.exe.4242.dmp" in names

    def test_collects_files_inside_wer_report_folders(self, tmp_path):
        roots = make_wer_layout(tmp_path)
        names = [p.name for p in find_crash_artifacts("myapp.exe", roots)]
        assert "Report.wer" in names
        assert "memory.hdmp" in names

    def test_other_apps_artifacts_are_ignored(self, tmp_path):
        roots = make_wer_layout(tmp_path)
        found = find_crash_artifacts("myapp.exe", roots)
        assert not any("other" in p.name.lower() for p in found)

    def test_matching_is_case_insensitive(self, tmp_path):
        roots = make_wer_layout(tmp_path)
        assert find_crash_artifacts("MYAPP.EXE", roots)

    def test_missing_roots_are_skipped_quietly(self, tmp_path):
        assert find_crash_artifacts("myapp.exe", [tmp_path / "nonexistent"]) == []

    def test_empty_executable_returns_nothing(self, tmp_path):
        roots = make_wer_layout(tmp_path)
        assert find_crash_artifacts("", roots) == []

    def test_non_dump_files_in_crashdumps_are_ignored(self, tmp_path):
        roots = make_wer_layout(tmp_path)
        names = [p.name for p in find_crash_artifacts("myapp.exe", roots)]
        assert "notes.txt" not in names
