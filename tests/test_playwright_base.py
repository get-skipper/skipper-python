"""Tests for skipper_playwright.SkipperSyncTest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from skipper_core import SkipperConfig, SkipperResolver, build_test_id, normalize_test_id
from skipper_core.credentials import FileCredentials
from skipper_playwright import SkipperSyncTest


def _make_config() -> SkipperConfig:
    return SkipperConfig(
        spreadsheet_id="fake-id",
        credentials=FileCredentials(path="./fake.json"),
    )


class TestSkipperSyncTestEnabled:
    """Tests that pass when the resolver reports the test as enabled."""

    skipper_config = _make_config()

    @classmethod
    def setup_class(cls) -> None:
        import threading

        resolver = SkipperResolver.__new__(SkipperResolver)
        resolver._cache = {}  # type: ignore[attr-defined]
        resolver._config = _make_config()  # type: ignore[attr-defined]
        resolver._client = None  # type: ignore[attr-defined]
        cls._skipper_resolver = resolver
        cls._skipper_discovered = []
        cls._skipper_lock = threading.Lock()
        cls._skipper_cache_dir = None

    def setup_method(self, method: object) -> None:
        if self._skipper_resolver is None:
            return
        # Call SkipperSyncTest.setup_method directly with the injected resolver.
        SkipperSyncTest.setup_method(self, method)  # type: ignore[arg-type]

    def test_enabled_test_runs(self) -> None:
        assert True


class TestSkipperSyncTestSkipped:
    """Verifies that setup_method raises pytest.skip.Exception for disabled tests."""

    def test_setup_method_skips_disabled_test(self) -> None:
        import inspect
        import threading

        future = datetime.now(tz=timezone.utc) + timedelta(days=5)
        resolver = SkipperResolver.__new__(SkipperResolver)
        resolver._cache = {}  # type: ignore[attr-defined]
        resolver._config = _make_config()  # type: ignore[attr-defined]
        resolver._client = None  # type: ignore[attr-defined]

        class FakeTest(SkipperSyncTest):
            skipper_config = _make_config()

            def test_something(self) -> None:
                pass

        instance = FakeTest.__new__(FakeTest)
        instance._skipper_resolver = resolver
        instance._skipper_discovered = []
        instance._skipper_lock = threading.Lock()
        instance._skipper_cache_dir = None

        # Inject disabled status for the method.
        file_path = inspect.getfile(FakeTest)
        test_id = normalize_test_id(build_test_id(file_path, ["FakeTest", "test_something"]))
        resolver._cache[test_id] = future  # type: ignore[index]

        with pytest.raises(pytest.skip.Exception):
            instance.setup_method(FakeTest.test_something)
