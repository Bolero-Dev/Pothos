"""Tests for event parsing and filtering against realistic wevtutil XML."""

from datetime import datetime, timedelta, timezone

from pothos.events import ErrorEvent, filter_events, parse_wevtutil_xml

NS = 'xmlns="http://schemas.microsoft.com/win/2004/08/events/event"'


def crash_event_xml(
    exe="myapp.exe",
    event_id=1000,
    level=2,
    system_time="2026-07-06T03:14:15.9265358Z",
    provider="Application Error",
    with_message=True,
):
    message = (
        f"<RenderingInfo Culture='en-US'><Message>"
        f"Faulting application name: {exe}, version: 1.2.3.0"
        f"</Message></RenderingInfo>"
        if with_message else ""
    )
    return f"""
    <Event {NS}>
      <System>
        <Provider Name='{provider}'/>
        <EventID>{event_id}</EventID>
        <Level>{level}</Level>
        <TimeCreated SystemTime='{system_time}'/>
        <Channel>Application</Channel>
      </System>
      <EventData>
        <Data>{exe}</Data>
        <Data>1.2.3.0</Data>
        <Data>kernelbase.dll</Data>
        <Data>0xc0000005</Data>
      </EventData>
      {message}
    </Event>
    """


class TestParsing:
    def test_parses_core_fields(self):
        events = parse_wevtutil_xml(crash_event_xml())
        assert len(events) == 1
        event = events[0]
        assert event.event_id == 1000
        assert event.level == 2
        assert event.level_name == "Error"
        assert event.provider == "Application Error"
        assert event.time_created.year == 2026
        assert "Faulting application name: myapp.exe" in event.message

    def test_seven_digit_fractional_seconds_are_handled(self):
        events = parse_wevtutil_xml(crash_event_xml(system_time="2026-07-06T03:14:15.9265358Z"))
        assert events[0].time_created.tzinfo is not None

    def test_missing_rendered_message_falls_back_to_data_values(self):
        events = parse_wevtutil_xml(crash_event_xml(with_message=False))
        assert "myapp.exe" in events[0].message
        assert "0xc0000005" in events[0].message

    def test_multiple_events_parse_without_root_element(self):
        xml = crash_event_xml() + crash_event_xml(event_id=1002)
        events = parse_wevtutil_xml(xml)
        assert [e.event_id for e in events] == [1000, 1002]

    def test_malformed_xml_returns_empty_rather_than_raising(self):
        assert parse_wevtutil_xml("<Event>unclosed") == []

    def test_raw_xml_is_preserved_for_the_event_file(self):
        events = parse_wevtutil_xml(crash_event_xml())
        assert "EventData" in events[0].raw_xml


class TestMatching:
    def test_matches_exe_in_event_data_case_insensitively(self):
        events = parse_wevtutil_xml(crash_event_xml(exe="MyApp.EXE", with_message=False))
        assert events[0].mentions("myapp.exe")

    def test_matches_exe_in_rendered_message(self):
        events = parse_wevtutil_xml(crash_event_xml())
        assert events[0].mentions("myapp.exe")

    def test_unrelated_executable_does_not_match(self):
        events = parse_wevtutil_xml(crash_event_xml())
        assert not events[0].mentions("otherapp.exe")


class TestFiltering:
    def _events(self):
        now = datetime.now(timezone.utc)
        recent = crash_event_xml(system_time=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"))
        old = crash_event_xml(system_time=(now - timedelta(hours=50)).isoformat().replace("+00:00", "Z"))
        info = crash_event_xml(
            level=4,
            system_time=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        )
        return parse_wevtutil_xml(recent + old + info)

    def test_time_window_excludes_old_events(self):
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        kept = filter_events(self._events(), "myapp.exe", since)
        assert len(kept) == 1

    def test_information_level_is_excluded_by_default(self):
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        kept = filter_events(self._events(), "myapp.exe", since)
        assert all(e.level <= 3 for e in kept)

    def test_results_sorted_newest_first(self):
        since = datetime.now(timezone.utc) - timedelta(hours=100)
        kept = filter_events(self._events(), "myapp.exe", since, max_level=3)
        times = [e.time_created for e in kept]
        assert times == sorted(times, reverse=True)

    def test_unrelated_executable_yields_nothing(self):
        since = datetime.now(timezone.utc) - timedelta(hours=100)
        assert filter_events(self._events(), "ghost.exe", since) == []
