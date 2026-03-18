# skipper-pytest

pytest plugin for [Skipper](https://github.com/get-skipper/skipper-python) test-gating via Google Spreadsheet.

Tests are automatically skipped when their `disabledUntil` date is in the future — no changes to test code required.

## Installation

```bash
pip install skipper-pytest
```

## Setup

Add to `tests/conftest.py`:

```python
from skipper_pytest import configure_skipper
from skipper_core import SkipperConfig, FileCredentials

configure_skipper(SkipperConfig(
    spreadsheet_id="YOUR_SPREADSHEET_ID",
    credentials=FileCredentials("./service-account-skipper-bot.json"),
    sheet_name="skipper-python",
))
```

Or configure entirely via environment variables:

```bash
SKIPPER_SPREADSHEET_ID=... \
SKIPPER_CREDENTIALS_FILE=./service-account-skipper-bot.json \
SKIPPER_SHEET_NAME=skipper-python \
pytest
```

## Test ID Format

`tests/test_auth.py > ClassName > test_method_name`

## Sync Mode

Set `SKIPPER_MODE=sync` to have Skipper reconcile the spreadsheet after the test run (adds new test IDs, removes stale ones).

See the [root README](../../README.md) for full documentation.
