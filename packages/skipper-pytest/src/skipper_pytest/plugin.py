"""skipper-pytest — pytest plugin for Skipper test-gating."""

from __future__ import annotations

import os
import threading

import pytest
from skipper_core import (
    CacheManager,
    SkipperConfig,
    SkipperResolver,
    build_test_id,
    mode_from_env,
)
from skipper_core.writer import SheetsWriter

# ── Module-level state ────────────────────────────────────────────────────────
_resolver: SkipperResolver | None = None
_cache_dir: str | None = None
_discovered_lock = threading.Lock()
_discovered_ids: list[str] = []
_config: SkipperConfig | None = None
_cache_manager = CacheManager()

# ── Public API ────────────────────────────────────────────────────────────────


def configure_skipper(config: SkipperConfig) -> None:
    """Call this from conftest.py to register a SkipperConfig with the plugin.

    Example::

        # tests/conftest.py
        from skipper_pytest import configure_skipper
        from skipper_core import SkipperConfig, FileCredentials

        configure_skipper(SkipperConfig(
            spreadsheet_id="YOUR_SPREADSHEET_ID",
            credentials=FileCredentials("./service-account-skipper-bot.json"),
            sheet_name="skipper-python",
        ))
    """
    global _config
    _config = config


# ── pytest hooks ──────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Initialize the resolver (or rehydrate from cache for xdist workers)."""
    global _resolver, _cache_dir, _discovered_ids

    _discovered_ids = []

    # xdist worker: rehydrate from cache file written by the controller.
    cache_file = os.getenv("SKIPPER_CACHE_FILE")
    if cache_file and _is_xdist_worker(config):
        data = _cache_manager.read_resolver_cache(cache_file)
        _resolver = SkipperResolver.from_marshal_cache(data)
        return

    # Main process (or no xdist): initialize from spreadsheet if config was provided.
    # Config may not be set yet (set_config is called in conftest.py which runs after
    # pytest_configure for plugins). We defer actual initialization to pytest_sessionstart.


def pytest_sessionstart(session: pytest.Session) -> None:
    """Initialize the resolver once config is available (called after conftest.py)."""
    global _resolver, _cache_dir

    if _resolver is not None:
        return  # already rehydrated (xdist worker)

    cfg = _config
    if cfg is None:
        # Check env vars as fallback for minimal config.
        cfg = _config_from_env()
    if cfg is None:
        return  # Skipper not configured — run all tests normally.

    if _is_xdist_worker(session.config):
        return  # Worker rehydration handled in pytest_configure.

    resolver = SkipperResolver(cfg)
    resolver.initialize()
    _resolver = resolver

    data = resolver.marshal_cache()
    cache_dir = _cache_manager.write_resolver_cache(data)
    _cache_dir = cache_dir
    os.environ["SKIPPER_CACHE_FILE"] = os.path.join(cache_dir, "cache.json")
    os.environ["SKIPPER_DISCOVERED_DIR"] = cache_dir


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip the test if Skipper says it is disabled; record the test ID for sync."""
    if _resolver is None:
        return

    test_id = _test_id_from_item(item)

    with _discovered_lock:
        _discovered_ids.append(test_id)

    # Also write to the shared dir if running under xdist.
    discovered_dir = os.getenv("SKIPPER_DISCOVERED_DIR")
    if discovered_dir and _is_xdist_worker(item.config):
        _cache_manager.write_discovered_ids(discovered_dir, [test_id])

    if not _resolver.is_test_enabled(test_id):
        until = _resolver.get_disabled_until(test_id)
        msg = "[skipper] Test disabled"
        if until is not None:
            msg += f" until {until.strftime('%Y-%m-%d')}"
        pytest.skip(msg)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """In sync mode, write discovered IDs and reconcile the spreadsheet."""
    if _resolver is None or _is_xdist_worker(session.config):
        return

    cfg = _config or _config_from_env()
    if cfg is None or mode_from_env().value != "sync":
        _cleanup()
        return

    # Flush in-memory discovered IDs to the shared dir.
    if _cache_dir:
        with _discovered_lock:
            ids = list(_discovered_ids)
        if ids:
            _cache_manager.write_discovered_ids(_cache_dir, ids)

        # Merge all workers' files.
        all_ids = _cache_manager.merge_discovered_ids(_cache_dir)
    else:
        with _discovered_lock:
            all_ids = list(_discovered_ids)

    writer = SheetsWriter(cfg)
    writer.sync(all_ids)

    _cleanup()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _test_id_from_item(item: pytest.Item) -> str:
    """Build a stable Skipper test ID from a pytest Item."""
    try:
        # item.fspath gives the absolute path; build_test_id makes it relative.
        file_path = str(item.fspath)
    except Exception:
        file_path = item.nodeid.split("::")[0]

    # nodeid is "path/to/test.py::ClassName::test_name[param]"
    parts = item.nodeid.split("::")
    title_parts = parts[1:]  # drop the file path component

    # Strip parametrize suffixes like "[param]" for lookup so that
    # test_login[chrome] and test_login[firefox] map to the same spreadsheet row.
    title_parts = [_strip_param(p) for p in title_parts]

    return build_test_id(file_path, title_parts)


def _strip_param(name: str) -> str:
    bracket = name.find("[")
    return name[:bracket] if bracket >= 0 else name


def _is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def _config_from_env() -> SkipperConfig | None:
    """Build a minimal SkipperConfig from environment variables."""
    from skipper_core import Base64Credentials, Credentials, FileCredentials

    spreadsheet_id = os.getenv("SKIPPER_SPREADSHEET_ID")
    if not spreadsheet_id:
        return None

    creds_file = os.getenv("SKIPPER_CREDENTIALS_FILE")
    creds_b64 = os.getenv("GOOGLE_CREDS_B64")

    credentials: Credentials
    if creds_file:
        credentials = FileCredentials(path=creds_file)
    elif creds_b64:
        credentials = Base64Credentials(encoded=creds_b64)
    else:
        return None

    return SkipperConfig(
        spreadsheet_id=spreadsheet_id,
        credentials=credentials,
        sheet_name=os.getenv("SKIPPER_SHEET_NAME") or None,
    )


def _cleanup() -> None:
    if _cache_dir:
        _cache_manager.cleanup(_cache_dir)
