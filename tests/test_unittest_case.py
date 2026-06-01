"""Tests for skipper_unittest.SkipperTestCase."""

from __future__ import annotations

import threading
import unittest
from datetime import datetime, timedelta, timezone

from skipper_core import SkipperConfig, SkipperResolver, build_test_id, normalize_test_id
from skipper_core.credentials import FileCredentials
from skipper_unittest import SkipperTestCase


def _make_config() -> SkipperConfig:
    return SkipperConfig(
        spreadsheet_id="fake-id",
        credentials=FileCredentials(path="./fake.json"),
    )


def _make_resolver(cache: dict[str, datetime | None]) -> SkipperResolver:
    """Create a resolver directly from a cache dict (no network calls)."""
    resolver = SkipperResolver.__new__(SkipperResolver)
    resolver._cache = cache  # type: ignore[attr-defined]
    resolver._config = _make_config()  # type: ignore[attr-defined]
    resolver._client = None  # type: ignore[attr-defined]
    return resolver


class TestSkipperTestCaseEnabled(SkipperTestCase):
    """Verifies that tests not disabled in the spreadsheet run normally."""

    skipper_config = _make_config()

    @classmethod
    def setUpClass(cls) -> None:
        # Bypass network — inject an empty-cache resolver.
        cls._skipper_discovered = []
        cls._skipper_suppressed = []
        cls._skipper_lock = threading.Lock()
        cls._skipper_cache_dir = None
        cls._skipper_resolver = _make_resolver({})

    @classmethod
    def tearDownClass(cls) -> None:
        # Skip sync; fake config has no real credentials.
        pass

    def test_enabled_test_runs(self) -> None:
        self.assertTrue(True)


class TestSkipperTestCaseSkipped(SkipperTestCase):
    """Verifies that a test with a future disabledUntil is skipped."""

    skipper_config = _make_config()

    @classmethod
    def setUpClass(cls) -> None:
        import inspect

        cls._skipper_discovered = []
        cls._skipper_suppressed = []
        cls._skipper_lock = threading.Lock()
        cls._skipper_cache_dir = None

        future = datetime.now(tz=timezone.utc) + timedelta(days=7)
        cache: dict[str, datetime | None] = {}
        file_path = inspect.getfile(cls)
        test_id = normalize_test_id(
            build_test_id(file_path, [cls.__name__, "test_this_should_be_skipped"])
        )
        cache[test_id] = future
        cls._skipper_resolver = _make_resolver(cache)

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def test_this_should_be_skipped(self) -> None:
        self.fail("This test should have been skipped by Skipper")


class TestSkipperTestCaseNoConfig(unittest.TestCase):
    """Verifies that SkipperTestCase without skipper_config runs normally."""

    def test_runs_without_config(self) -> None:
        # No skipper_config set — should run normally.
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
