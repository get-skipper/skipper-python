"""skipper-unittest — unittest.TestCase mixin for Skipper test-gating."""

from __future__ import annotations

import inspect
import os
import threading
import unittest

from skipper_core import (
    CacheManager,
    SkipperConfig,
    SkipperResolver,
    build_report,
    build_test_id,
    emit_summary,
    mode_from_env,
)
from skipper_core.writer import SheetsWriter

_cache_manager = CacheManager()
_discovered_lock = threading.Lock()


class SkipperTestCase(unittest.TestCase):
    """A unittest.TestCase mixin that automatically skips disabled tests.

    Set the ``skipper_config`` class attribute to a :class:`~skipper_core.SkipperConfig`
    instance. The resolver is initialised once per test class (in ``setUpClass``).

    Example::

        class AuthTests(SkipperTestCase):
            skipper_config = SkipperConfig(
                spreadsheet_id="YOUR_SPREADSHEET_ID",
                credentials=FileCredentials("./service-account-skipper-bot.json"),
                sheet_name="skipper-python",
            )

            def test_login(self):
                ...  # auto-skipped when disabled in the spreadsheet
    """

    skipper_config: SkipperConfig  # set by subclass

    _skipper_resolver: SkipperResolver | None = None
    _skipper_cache_dir: str | None = None
    _skipper_discovered: list[str]
    _skipper_suppressed: list[str]
    _skipper_lock: threading.Lock

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls._skipper_discovered = []
        cls._skipper_suppressed = []
        cls._skipper_lock = threading.Lock()

        cfg = getattr(cls, "skipper_config", None)
        if cfg is None:
            return

        # Rehydrate from cache file if available (e.g., orchestrated by another process).
        cache_file = os.getenv("SKIPPER_WORKER_CACHE_FILE")
        if cache_file:
            data = _cache_manager.read_resolver_cache(cache_file)
            cls._skipper_resolver = SkipperResolver.from_marshal_cache(data)
            return

        resolver = SkipperResolver(cfg)
        resolver.initialize()
        cls._skipper_resolver = resolver

        data = resolver.marshal_cache()
        cache_dir = _cache_manager.write_resolver_cache(data)
        cls._skipper_cache_dir = cache_dir
        os.environ["SKIPPER_WORKER_CACHE_FILE"] = os.path.join(cache_dir, "cache.json")
        os.environ["SKIPPER_DISCOVERED_DIR"] = cache_dir

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls._skipper_resolver is not None:
                import datetime as _dt

                with cls._skipper_lock:
                    discovered = list(cls._skipper_discovered)
                    suppressed = list(cls._skipper_suppressed)

                all_entries = cls._skipper_resolver.get_all_entries()
                now = _dt.datetime.now(tz=_dt.timezone.utc)
                re_enabled = [
                    tid
                    for tid in discovered
                    if tid not in suppressed
                    and tid in all_entries
                    and all_entries[tid] is not None
                    and all_entries[tid] <= now  # type: ignore[operator]
                ]
                report = build_report(all_entries, suppressed, re_enabled)
                emit_summary(report)

            cfg = getattr(cls, "skipper_config", None)
            if cfg is not None and mode_from_env().value == "sync":
                with cls._skipper_lock:
                    ids = list(cls._skipper_discovered)

                if cls._skipper_cache_dir:
                    _cache_manager.write_discovered_ids(cls._skipper_cache_dir, ids)
                    all_ids = _cache_manager.merge_discovered_ids(cls._skipper_cache_dir)
                else:
                    all_ids = ids

                writer = SheetsWriter(cfg)
                writer.sync(all_ids)
        finally:
            if cls._skipper_cache_dir:
                _cache_manager.cleanup(cls._skipper_cache_dir)
                cls._skipper_cache_dir = None
            super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()

        if self._skipper_resolver is None:
            return

        file_path = inspect.getfile(type(self))
        test_id = build_test_id(file_path, [type(self).__name__, self._testMethodName])

        with self._skipper_lock:
            self._skipper_discovered.append(test_id)

        if not self._skipper_resolver.is_test_enabled(test_id):
            until = self._skipper_resolver.get_disabled_until(test_id)
            msg = "[skipper] Test disabled"
            if until is not None:
                msg += f" until {until.strftime('%Y-%m-%d')}"
            with self._skipper_lock:
                self._skipper_suppressed.append(test_id)
            self.skipTest(msg)
