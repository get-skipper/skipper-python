# skipper-playwright

Playwright integration for [Skipper](https://github.com/get-skipper/skipper-python) test-gating via Google Spreadsheet.

## Installation

```bash
pip install skipper-playwright playwright
playwright install
```

## Setup

Inherit from `SkipperSyncTest` instead of writing plain test functions:

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
        page.goto("https://example.com")
        ...
```

## Test ID Format

`tests/test_login.py > ClassName > test_method_name`

See the [root README](../../README.md) for full documentation.
