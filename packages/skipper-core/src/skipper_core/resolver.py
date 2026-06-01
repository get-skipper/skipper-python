from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import SheetsClient
from .config import SkipperConfig
from .logger import log, logf, warn
from .testid import normalize_test_id

_DEFAULT_API_CACHE_FILE = ".skipper-cache.json"
_DEFAULT_CACHE_TTL = 300


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
        """Fetch the spreadsheet and populate the internal cache.

        On API failure falls back to a local cache file (SKIPPER_CACHE_FILE,
        default .skipper-cache.json) if it is fresher than SKIPPER_CACHE_TTL
        seconds (default 300). If neither succeeds and SKIPPER_FAIL_OPEN is
        true (default) all tests run; otherwise the exception is re-raised.
        """
        log("initializing resolver")
        api_cache_file = os.environ.get("SKIPPER_CACHE_FILE", _DEFAULT_API_CACHE_FILE)
        cache_ttl = int(os.environ.get("SKIPPER_CACHE_TTL", str(_DEFAULT_CACHE_TTL)))
        fail_open = os.environ.get("SKIPPER_FAIL_OPEN", "true").lower() != "false"

        try:
            result = self._client.fetch_all()
            for entry in result.entries:
                nid = normalize_test_id(entry.test_id)
                self._cache[nid] = entry.disabled_until
            logf("loaded %d test entries from spreadsheet", len(self._cache))
            _write_api_cache(api_cache_file, self._cache)
        except Exception as exc:
            cached = _read_api_cache(api_cache_file, cache_ttl)
            if cached is not None:
                age = time.time() - cached["ts"]
                warn(f"API failed ({exc}), using cache ({age:.0f}s old)")
                self._cache = cached["entries"]
                return
            if fail_open:
                warn(f"API failed ({exc}), no valid cache — running all tests (fail-open)")
                return
            raise

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

    def get_all_entries(self) -> dict[str, datetime | None]:
        """Return a snapshot of all entries in the resolver cache."""
        return dict(self._cache)

    def marshal_cache(self) -> bytes:
        """Serialize the cache to JSON bytes for cross-process sharing."""
        out: dict[str, str | None] = {}
        for k, v in self._cache.items():
            out[k] = v.isoformat() if v is not None else None
        return json.dumps(out).encode()

    @classmethod
    def from_marshal_cache(cls, data: bytes) -> SkipperResolver:
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


# ── Persistent API cache helpers ──────────────────────────────────────────────


def _write_api_cache(path: str, cache: dict[str, datetime | None]) -> None:
    """Persist the resolver cache to disk for use as an API-failure fallback."""
    try:
        serialized: dict[str, str | None] = {
            k: v.isoformat() if v is not None else None for k, v in cache.items()
        }
        payload = json.dumps({"ts": time.time(), "entries": serialized})
        Path(path).write_text(payload, encoding="utf-8")
    except Exception as exc:
        warn(f"could not write API cache to {path!r}: {exc}")


def _read_api_cache(
    path: str, ttl: int
) -> dict[str, Any] | None:
    """Read the persistent API cache if it exists and is within TTL.

    Returns a dict with keys ``ts`` (float) and ``entries``
    (dict[str, datetime | None]), or None if the cache is absent/expired/corrupt.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        age = time.time() - float(raw["ts"])
        if age > ttl:
            return None
        entries: dict[str, datetime | None] = {}
        for k, v in raw["entries"].items():
            entries[k] = datetime.fromisoformat(v) if v is not None else None
        return {"ts": raw["ts"], "entries": entries}
    except Exception:
        return None
