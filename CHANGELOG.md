# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] – 2026-06-01

### Added

- **`SKIPPER_FAIL_OPEN`** (default `true`): when the Google Sheets API is
  unreachable and no usable disk cache exists, `initialize()` returns normally
  with an empty cache, allowing all tests to run unblocked.
- **`SKIPPER_CACHE_FILE`** (default `.skipper-cache.json`) and
  **`SKIPPER_CACHE_TTL`** (default `300` seconds): after every successful API
  fetch the resolved cache is persisted to disk. On the next `initialize()` call,
  if the API is unavailable the file is used as a fallback as long as it is
  younger than the configured TTL.
- **`SKIPPER_SYNC_ALLOW_DELETE`** (default `false`): orphaned rows in the
  Google Sheet are no longer deleted automatically during a sync. Set to `true`
  to opt-in to the previous pruning behaviour and avoid accidental data loss.
- **Quarantine debt CI summary** (`skipper_core.report`): at the end of every
  test session a structured report is emitted — to `GITHUB_STEP_SUMMARY` when
  running on GitHub Actions, otherwise to stdout — and written to
  `skipper-report.json`. The report includes: number of currently suppressed
  tests, tests expiring this week, tests re-enabled in this run, and a
  *quarantine-days debt* score (sum of `disabled_until − today` across all
  active rows). Wired into `skipper-pytest` (`pytest_sessionfinish`),
  `skipper-unittest` (`tearDownClass`), and `skipper-playwright`
  (`teardown_class`).

### Fixed

- **Strict `disabledUntil` date parsing**: replaced the lenient multi-format
  parser with a strict `YYYY-MM-DD`-only implementation. Partial dates, locale
  formats, and datetime strings are now rejected immediately with a row-numbered
  error instead of being silently ignored.
- **Timezone-consistent expiry**: dates are parsed in UTC and stored as
  midnight UTC of the day *after* the given date (e.g. `2026-04-01` expires at
  `2026-04-02T00:00:00Z`). All CI runners reach the same expiry instant
  regardless of their local timezone.
- Empty or whitespace `disabledUntil` values continue to be treated as "not
  disabled" (no error).

## [1.0.0] – 2026-03-18

### Added

- Initial release: `skipper-core` package with `SkipperResolver`,
  `SheetsClient`, `SheetsWriter`, `CacheManager`, credential helpers
  (`FileCredentials`, `Base64Credentials`, `ServiceAccountCredentials`), and
  test-ID normalisation utilities.
- `skipper-pytest`: pytest plugin (registered via `pytest11` entry point) with
  automatic test skipping and sync mode.
- `skipper-unittest`: `SkipperTestCase(unittest.TestCase)` mixin for standard
  unittest-based suites.
- `skipper-playwright`: `SkipperSyncTest` base class for pytest-playwright
  synchronous tests.
- `SKIPPER_MODE` env var (`read-only` / `sync`).
- `SKIPPER_DEBUG` env var for verbose logging.
- Reference-sheet support for shared disabled-test lists across multiple sheets.
- xdist support: resolver cache serialised and shared across worker processes
  via `SKIPPER_WORKER_CACHE_FILE`.

[Unreleased]: https://github.com/get-skipper/skipper-python/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/get-skipper/skipper-python/compare/v1.0.0...v1.2.0
[1.0.0]: https://github.com/get-skipper/skipper-python/releases/tag/v1.0.0
