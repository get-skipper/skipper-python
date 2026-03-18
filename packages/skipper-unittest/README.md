# skipper-unittest

unittest integration for [Skipper](https://github.com/get-skipper/skipper-python) test-gating via Google Spreadsheet.

## Installation

```bash
pip install skipper-unittest
```

## Setup

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

## Test ID Format

`tests/test_auth.py > ClassName > test_method_name`

See the [root README](../../README.md) for full documentation.
