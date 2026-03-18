# skipper-python

A Python test-gating library that dynamically enables and disables tests via a Google Spreadsheet — without modifying test code.

Supported frameworks: **pytest**, **unittest**, **Playwright**.

---

## How It Works

Skipper reads a Google Sheet at test startup and checks each test against a `disabledUntil` date:

- If the date is in the **future**, the test is **skipped**.
- If the date is in the **past**, empty, or the test is **not in the sheet**, it **runs normally**.

This means you can temporarily disable a flaky test by entering a future date in the spreadsheet, without touching any code or CI pipeline.

Skipper operates in two modes:

| Mode | Behaviour |
|------|-----------|
| `read-only` (default) | Fetches the spreadsheet at test startup; skips disabled tests. |
| `sync` | Also reconciles the spreadsheet: adds new test IDs and removes stale ones. |

---

## Spreadsheet Schema

| Column | Required | Default header | Description |
|--------|----------|----------------|-------------|
| Test ID | ✅ | `testId` | Canonical test identifier (see format below) |
| Disabled Until | ❌ | `disabledUntil` | ISO date (`YYYY-MM-DD`); empty = test is enabled |
| Notes | ❌ | `notes` | Free-text notes |

**Test ID format:** `path/to/test_file.py > ClassName > test_method_name`

---

## Installation

```bash
pip install skipper-pytest       # for pytest
pip install skipper-unittest     # for unittest
pip install skipper-playwright   # for Playwright
```

---

## Google Sheets Setup

1. Create a Google Cloud project and enable the **Google Sheets API**.
2. Create a **Service Account** and download the JSON key.
3. Share your spreadsheet with the service account email (Editor access).
4. Store the key as a file (`service-account.json`) or as a base64-encoded secret:
   ```bash
   base64 -i service-account.json | tr -d '\n'
   ```

---

## pytest Setup

```python
# tests/conftest.py
from skipper_pytest import configure_skipper
from skipper_core import SkipperConfig, FileCredentials

configure_skipper(SkipperConfig(
    spreadsheet_id="YOUR_SPREADSHEET_ID",
    credentials=FileCredentials("./service-account-skipper-bot.json"),
    sheet_name="skipper-python",
))
```

Or via environment variables (no `conftest.py` changes needed):

```bash
SKIPPER_SPREADSHEET_ID=... \
SKIPPER_CREDENTIALS_FILE=./service-account-skipper-bot.json \
SKIPPER_SHEET_NAME=skipper-python \
pytest
```

---

## unittest Setup

```python
from skipper_unittest import SkipperTestCase
from skipper_core import SkipperConfig, FileCredentials

class AuthTests(SkipperTestCase):
    skipper_config = SkipperConfig(
        spreadsheet_id="YOUR_SPREADSHEET_ID",
        credentials=FileCredentials("./service-account-skipper-bot.json"),
        sheet_name="skipper-python",
    )

    def test_login(self):
        ...  # auto-skipped when disabled in the spreadsheet
```

---

## Playwright Setup

```python
from skipper_playwright import SkipperSyncTest
from skipper_core import SkipperConfig, FileCredentials
from playwright.sync_api import Page

class LoginTests(SkipperSyncTest):
    skipper_config = SkipperConfig(
        spreadsheet_id="YOUR_SPREADSHEET_ID",
        credentials=FileCredentials("./service-account-skipper-bot.json"),
        sheet_name="skipper-python",
    )

    def test_login(self, page: Page):
        ...
```

---

## Configuration Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `spreadsheet_id` | `str` | — | Google Spreadsheet ID (from URL) |
| `credentials` | `Credentials` | — | Service account credentials |
| `sheet_name` | `str \| None` | First sheet | Target sheet tab name |
| `reference_sheets` | `tuple[str, ...]` | `()` | Read-only sheets merged into the resolver |
| `test_id_column` | `str` | `"testId"` | Column header for test IDs |
| `disabled_until_column` | `str` | `"disabledUntil"` | Column header for dates |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SKIPPER_MODE` | `"read-only"` (default) or `"sync"` |
| `SKIPPER_SPREADSHEET_ID` | Spreadsheet ID (alternative to code config) |
| `SKIPPER_CREDENTIALS_FILE` | Path to service account JSON |
| `GOOGLE_CREDS_B64` | Base64-encoded service account JSON |
| `SKIPPER_SHEET_NAME` | Sheet tab name |
| `SKIPPER_DEBUG` | Any value enables debug logging |

---

## CI Example (GitHub Actions)

```yaml
# .github/workflows/ci.yml
- name: Run tests (read-only)
  run: pytest
  env:
    SKIPPER_SPREADSHEET_ID: ${{ secrets.SKIPPER_SPREADSHEET_ID }}
    GOOGLE_CREDS_B64: ${{ secrets.GOOGLE_CREDS_B64 }}
    SKIPPER_SHEET_NAME: skipper-python

# .github/workflows/sync.yml (runs on merge to main)
- name: Run tests (sync)
  run: pytest
  env:
    SKIPPER_MODE: sync
    SKIPPER_SPREADSHEET_ID: ${{ secrets.SKIPPER_SPREADSHEET_ID }}
    GOOGLE_CREDS_B64: ${{ secrets.GOOGLE_CREDS_B64 }}
    SKIPPER_SHEET_NAME: skipper-python
```

---

## Development

```bash
make install    # uv sync --all-packages
make test       # run unit tests
make lint       # ruff check + format
make typecheck  # mypy
make build      # build all wheels
```

---

## License

MIT — see [LICENSE](LICENSE).
