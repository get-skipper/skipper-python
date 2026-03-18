from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .client import SheetsClient
from .config import SkipperConfig
from .logger import log, logf
from .testid import normalize_test_id


class SkipperResolver:
    """Fetches a Google Spreadsheet and determines whether tests should run.

    Usage::

        resolver = SkipperResolver(config)
        resolver.initialize()          # fetches spreadsheet once
        if not resolver.is_test_enabled("tests/test_auth.py > test_login"):
            pytest.skip("disabled")
    """

    def __init__(self, config: SkipperConfig) -> None:
        self._config = config
        self._client = SheetsClient(config)
        # Normalized test ID → disabledUntil (None means "in sheet, no date")
        self._cache: dict[str, datetime | None] = {}

    def initialize(self) -> None:
        """Fetch the spreadsheet and populate the internal cache. Call once before use."""
        log("initializing resolver")
        result = self._client.fetch_all()
        for entry in result.entries:
            nid = normalize_test_id(entry.test_id)
            self._cache[nid] = entry.disabled_until
        logf("loaded %d test entries from spreadsheet", len(self._cache))

    def is_test_enabled(self, test_id: str) -> bool:
        """Return True if the test should run.

        - Tests not in the spreadsheet always run (opt-out model).
        - Tests with no date, or a past/today date, run normally.
        - Tests with a future disabledUntil date are skipped.
        """
        nid = normalize_test_id(test_id)
        if nid not in self._cache:
            return True
        disabled_until = self._cache[nid]
        if disabled_until is None:
            return True
        now = datetime.now(tz=timezone.utc)
        # Make naive datetimes comparable by treating them as UTC.
        if disabled_until.tzinfo is None:
            disabled_until = disabled_until.replace(tzinfo=timezone.utc)
        return disabled_until <= now

    def get_disabled_until(self, test_id: str) -> datetime | None:
        """Return the disabledUntil date for a test, or None if not set."""
        nid = normalize_test_id(test_id)
        return self._cache.get(nid)

    def marshal_cache(self) -> bytes:
        """Serialize the cache to JSON bytes for cross-process sharing."""
        out: dict[str, str | None] = {}
        for k, v in self._cache.items():
            out[k] = v.isoformat() if v is not None else None
        return json.dumps(out).encode()

    @classmethod
    def from_marshal_cache(cls, data: bytes) -> "SkipperResolver":
        """Rehydrate a resolver from bytes produced by marshal_cache."""
        raw: dict[str, Any] = json.loads(data)
        cache: dict[str, datetime | None] = {}
        for k, v in raw.items():
            if v is None:
                cache[k] = None
            else:
                cache[k] = datetime.fromisoformat(v)
        resolver = cls.__new__(cls)
        resolver._cache = cache
        resolver._config = None  # type: ignore[assignment]
        resolver._client = None  # type: ignore[assignment]
        return resolver
