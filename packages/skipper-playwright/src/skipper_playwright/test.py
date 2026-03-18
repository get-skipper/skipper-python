"""skipper-playwright — Playwright base class for Skipper test-gating."""

from __future__ import annotations

import inspect
import os
import threading
from typing import Any

import pytest
from skipper_core import (
    CacheManager,
    SkipperConfig,
    SkipperResolver,
    build_test_id,
    mode_from_env,
)
from skipper_core.writer import SheetsWriter

_cache_manager = CacheManager()


class SkipperSyncTest:
    """Base class for synchronous Playwright tests (pytest-playwright style).

    Inherit from this class instead of using raw pytest functions to get
    automatic test-gating. Set ``skipper_config`` as a class attribute.

    Example::

        from playwright.sync_api import Page

        class LoginTests(SkipperSyncTest):
            skipper_config = SkipperConfig(
                spreadsheet_id="YOUR_SPREADSHEET_ID",
                credentials=FileCredentials("./service-account-skipper-bot.json"),
                sheet_name="skipper-python",
            )

            def test_login(self, page: Page):
                ...
    """

    skipper_config: SkipperConfig  # set by subclass

    _skipper_resolver: SkipperResolver | None = None
    _skipper_cache_dir: str | None = None
    _skipper_discovered: list[str]
    _skipper_lock: threading.Lock

    @classmethod
    def setup_class(cls) -> None:
        cls._skipper_discovered = []
        cls._skipper_lock = threading.Lock()

        cfg = getattr(cls, "skipper_config", None)
        if cfg is None:
            return

        cache_file = os.getenv("SKIPPER_CACHE_FILE")
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
        os.environ["SKIPPER_CACHE_FILE"] = os.path.join(cache_dir, "cache.json")
        os.environ["SKIPPER_DISCOVERED_DIR"] = cache_dir

    @classmethod
    def teardown_class(cls) -> None:
        try:
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

    def setup_method(self, method: Any) -> None:
        if self._skipper_resolver is None:
            return

        file_path = inspect.getfile(type(self))
        test_id = build_test_id(file_path, [type(self).__name__, method.__name__])

        with self._skipper_lock:
            self._skipper_discovered.append(test_id)

        if not self._skipper_resolver.is_test_enabled(test_id):
            until = self._skipper_resolver.get_disabled_until(test_id)
            msg = "[skipper] Test disabled"
            if until is not None:
                msg += f" until {until.strftime('%Y-%m-%d')}"
            pytest.skip(msg)
