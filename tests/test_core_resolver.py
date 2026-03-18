"""Tests for skipper_core.SkipperResolver."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from skipper_core import SkipperConfig, SkipperResolver
from skipper_core.client import FetchAllResult, SheetFetchResult, TestEntry
from skipper_core.credentials import FileCredentials


def _make_config() -> SkipperConfig:
    return SkipperConfig(
        spreadsheet_id="fake-spreadsheet-id",
        credentials=FileCredentials(path="./service-account.json"),
    )


def _make_fetch_result(entries: list[TestEntry]) -> FetchAllResult:
    primary = SheetFetchResult(
        sheet_name="Sheet1",
        sheet_id=0,
        header=["testId", "disabledUntil", "notes"],
        entries=entries,
    )
    return FetchAllResult(primary=primary, entries=entries, service=MagicMock())


class TestIsTestEnabled:
    def test_unknown_test_is_enabled(self) -> None:
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result([])):
            resolver.initialize()
        assert resolver.is_test_enabled("tests/test_foo.py > test_unknown") is True

    def test_test_with_null_date_is_enabled(self) -> None:
        entries = [TestEntry(test_id="tests/test_foo.py > test_no_date", disabled_until=None)]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()
        assert resolver.is_test_enabled("tests/test_foo.py > test_no_date") is True

    def test_test_with_past_date_is_enabled(self) -> None:
        past = datetime.now(tz=timezone.utc) - timedelta(days=1)
        entries = [TestEntry(test_id="tests/test_foo.py > test_past", disabled_until=past)]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()
        assert resolver.is_test_enabled("tests/test_foo.py > test_past") is True

    def test_test_with_future_date_is_disabled(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(days=7)
        entries = [TestEntry(test_id="tests/test_foo.py > test_future", disabled_until=future)]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()
        assert resolver.is_test_enabled("tests/test_foo.py > test_future") is False

    def test_matching_is_case_insensitive(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(days=1)
        entries = [TestEntry(test_id="Tests/Test_Foo.py > Test_Login", disabled_until=future)]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()
        assert resolver.is_test_enabled("tests/test_foo.py > test_login") is False

    def test_not_initialized_raises(self) -> None:
        resolver = SkipperResolver(_make_config())
        # Should return True for unknown test even without initialization
        # (empty cache = all enabled).
        assert resolver.is_test_enabled("anything") is True


class TestGetDisabledUntil:
    def test_returns_none_for_unknown_test(self) -> None:
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result([])):
            resolver.initialize()
        assert resolver.get_disabled_until("tests/test_foo.py > test_x") is None

    def test_returns_date_for_disabled_test(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(days=5)
        entries = [TestEntry(test_id="tests/test_foo.py > test_x", disabled_until=future)]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()
        result = resolver.get_disabled_until("tests/test_foo.py > test_x")
        assert result is not None
        assert abs((result - future).total_seconds()) < 1


class TestMarshalCache:
    def test_round_trip(self) -> None:
        future = datetime(2030, 6, 1, tzinfo=timezone.utc)
        entries = [
            TestEntry(test_id="tests/test_a.py > test_one", disabled_until=future),
            TestEntry(test_id="tests/test_b.py > test_two", disabled_until=None),
        ]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()

        data = resolver.marshal_cache()
        restored = SkipperResolver.from_marshal_cache(data)

        assert restored.is_test_enabled("tests/test_a.py > test_one") is False
        assert restored.is_test_enabled("tests/test_b.py > test_two") is True
        assert restored.is_test_enabled("tests/test_c.py > test_three") is True

    def test_marshal_produces_valid_json(self) -> None:
        import json

        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result([])):
            resolver.initialize()
        data = resolver.marshal_cache()
        parsed = json.loads(data)
        assert isinstance(parsed, dict)
