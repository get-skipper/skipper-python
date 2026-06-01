"""Tests for skipper_core.SkipperResolver."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from skipper_core import SkipperConfig, SkipperResolver
from skipper_core.client import FetchAllResult, SheetFetchResult, TestEntry
from skipper_core.credentials import FileCredentials
from skipper_core.resolver import _read_api_cache, _write_api_cache


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


class TestFailOpen:
    def test_fail_open_true_runs_all_tests_on_api_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("SKIPPER_FAIL_OPEN", "true")
        monkeypatch.setenv("SKIPPER_CACHE_FILE", str(tmp_path / "cache.json"))
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", side_effect=RuntimeError("API down")):
            resolver.initialize()
        # Empty cache → all tests enabled (fail-open)
        assert resolver.is_test_enabled("tests/anything.py > test_x") is True

    def test_fail_open_false_reraises_on_api_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("SKIPPER_FAIL_OPEN", "false")
        monkeypatch.setenv("SKIPPER_CACHE_FILE", str(tmp_path / "cache.json"))
        resolver = SkipperResolver(_make_config())
        with (
            patch.object(resolver._client, "fetch_all", side_effect=RuntimeError("API down")),
            pytest.raises(RuntimeError, match="API down"),
        ):
            resolver.initialize()

    def test_uses_cache_on_api_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cache_path = str(tmp_path / "cache.json")
        monkeypatch.setenv("SKIPPER_CACHE_FILE", cache_path)
        monkeypatch.setenv("SKIPPER_CACHE_TTL", "300")

        future = datetime.now(tz=timezone.utc) + timedelta(days=7)
        warm_cache: dict[str, datetime | None] = {"tests/test_foo.py > test_disabled": future}
        _write_api_cache(cache_path, warm_cache)

        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", side_effect=RuntimeError("API down")):
            resolver.initialize()

        assert resolver.is_test_enabled("tests/test_foo.py > test_disabled") is False

    def test_ignores_expired_cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        cache_path = str(tmp_path / "cache.json")
        monkeypatch.setenv("SKIPPER_FAIL_OPEN", "true")
        monkeypatch.setenv("SKIPPER_CACHE_FILE", cache_path)
        monkeypatch.setenv("SKIPPER_CACHE_TTL", "1")

        future = datetime.now(tz=timezone.utc) + timedelta(days=7)
        warm_cache: dict[str, datetime | None] = {"tests/test_foo.py > test_disabled": future}
        _write_api_cache(cache_path, warm_cache)

        # Expire the cache by backdating the timestamp.
        raw = json.loads(Path(cache_path).read_text())
        raw["ts"] = time.time() - 10
        Path(cache_path).write_text(json.dumps(raw))

        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", side_effect=RuntimeError("API down")):
            resolver.initialize()

        # Expired cache ignored → fail-open → test enabled
        assert resolver.is_test_enabled("tests/test_foo.py > test_disabled") is True

    def test_writes_api_cache_on_success(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cache_path = str(tmp_path / "api.json")
        monkeypatch.setenv("SKIPPER_CACHE_FILE", cache_path)

        future = datetime.now(tz=timezone.utc) + timedelta(days=3)
        entries = [TestEntry(test_id="tests/a.py > test_x", disabled_until=future)]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()

        assert Path(cache_path).exists()
        cached = _read_api_cache(cache_path, ttl=300)
        assert cached is not None
        assert "tests/a.py > test_x" in cached["entries"]


class TestGetAllEntries:
    def test_returns_all_entries(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(days=5)
        entries = [
            TestEntry(test_id="tests/a.py > test_one", disabled_until=future),
            TestEntry(test_id="tests/b.py > test_two", disabled_until=None),
        ]
        resolver = SkipperResolver(_make_config())
        with patch.object(resolver._client, "fetch_all", return_value=_make_fetch_result(entries)):
            resolver.initialize()
        all_entries = resolver.get_all_entries()
        assert len(all_entries) == 2
        assert "tests/a.py > test_one" in all_entries
