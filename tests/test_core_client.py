"""Tests for skipper_core.SheetsClient date parsing and merge logic."""

from __future__ import annotations

from datetime import datetime, timezone

from skipper_core.client import TestEntry, _merge_entries, _more_restrictive, _parse_date


class TestParseDate:
    def test_parses_iso_date(self) -> None:
        dt = _parse_date("2026-06-01")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 6
        assert dt.day == 1

    def test_parses_rfc3339(self) -> None:
        dt = _parse_date("2026-06-01T12:00:00Z")
        assert dt is not None
        assert dt.year == 2026

    def test_parses_datetime_without_timezone(self) -> None:
        dt = _parse_date("2026-06-01T12:00:00")
        assert dt is not None

    def test_returns_none_for_invalid(self) -> None:
        assert _parse_date("not-a-date") is None
        assert _parse_date("01/06/2026") is None

    def test_returns_none_for_empty(self) -> None:
        assert _parse_date("") is None


class TestMoreRestrictive:
    def test_none_candidate_is_not_more_restrictive(self) -> None:
        current = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert _more_restrictive(None, current) is False

    def test_none_current_makes_candidate_more_restrictive(self) -> None:
        candidate = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert _more_restrictive(candidate, None) is True

    def test_later_candidate_is_more_restrictive(self) -> None:
        candidate = datetime(2030, 6, 1, tzinfo=timezone.utc)
        current = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert _more_restrictive(candidate, current) is True

    def test_earlier_candidate_is_not_more_restrictive(self) -> None:
        candidate = datetime(2030, 1, 1, tzinfo=timezone.utc)
        current = datetime(2030, 6, 1, tzinfo=timezone.utc)
        assert _more_restrictive(candidate, current) is False


class TestMergeEntries:
    def test_new_entries_are_appended(self) -> None:
        incoming = [TestEntry(test_id="tests/a.py > test_x", disabled_until=None)]
        result = _merge_entries([], incoming)
        assert len(result) == 1
        assert result[0].test_id == "tests/a.py > test_x"

    def test_duplicate_keeps_most_restrictive_date(self) -> None:
        later = datetime(2030, 6, 1, tzinfo=timezone.utc)
        earlier = datetime(2030, 1, 1, tzinfo=timezone.utc)
        existing = [TestEntry(test_id="tests/a.py > test_x", disabled_until=earlier)]
        incoming = [TestEntry(test_id="tests/a.py > test_x", disabled_until=later)]
        result = _merge_entries(existing, incoming)
        assert len(result) == 1
        assert result[0].disabled_until == later

    def test_case_insensitive_deduplication(self) -> None:
        later = datetime(2030, 6, 1, tzinfo=timezone.utc)
        existing = [TestEntry(test_id="tests/a.py > Test_X", disabled_until=None)]
        incoming = [TestEntry(test_id="tests/a.py > test_x", disabled_until=later)]
        result = _merge_entries(existing, incoming)
        assert len(result) == 1
        assert result[0].disabled_until == later

    def test_non_overlapping_entries_preserved(self) -> None:
        existing = [TestEntry(test_id="tests/a.py > test_a", disabled_until=None)]
        incoming = [TestEntry(test_id="tests/b.py > test_b", disabled_until=None)]
        result = _merge_entries(existing, incoming)
        assert len(result) == 2
