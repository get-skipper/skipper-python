# skipper-core

Core Google Sheets client and resolver for the Skipper test-gating system.

This package contains the shared logic used by all Skipper framework integrations:
- `SkipperResolver` — initialises from a Google Sheet and answers `is_test_enabled(test_id)`
- `SheetsClient` — authenticates and fetches spreadsheet data
- `SheetsWriter` — reconciles the spreadsheet in sync mode
- `CacheManager` — cross-process cache sharing for parallel test runners
- `build_test_id` / `normalize_test_id` — canonical test ID helpers
- Credential types: `FileCredentials`, `Base64Credentials`, `ServiceAccountCredentials`

See the [root README](../../README.md) for full documentation.

## Installation

```bash
pip install skipper-core
```

## Usage

```python
from skipper_core import SkipperConfig, SkipperResolver, FileCredentials

config = SkipperConfig(
    spreadsheet_id="YOUR_SPREADSHEET_ID",
    credentials=FileCredentials("./service-account.json"),
    sheet_name="skipper-python",
)

resolver = SkipperResolver(config)
resolver.initialize()

if not resolver.is_test_enabled("tests/test_auth.py > test_login"):
    pytest.skip("[skipper] Test disabled")
```
