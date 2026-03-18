# Contributing to skipper-python

## Setup

```bash
git clone https://github.com/get-skipper/skipper-python
cd skipper-python
make install
```

## Running Tests

```bash
make test          # unit tests only (no credentials required)
make lint          # ruff check + format
make typecheck     # mypy strict
```

## Project Structure

```
packages/
  skipper-core/        # shared resolver, client, cache
  skipper-pytest/      # pytest plugin (pytest11 entry point)
  skipper-unittest/    # unittest.TestCase mixin
  skipper-playwright/  # Playwright base class
tests/                 # unified test suite
```

## Running Integration Tests

Copy the service account JSON to the repo root (gitignored):

```bash
cp /path/to/service-account-skipper-bot.json .
```

Then run in sync mode to verify the spreadsheet is updated:

```bash
SKIPPER_MODE=sync \
SKIPPER_SPREADSHEET_ID=<id> \
SKIPPER_SHEET_NAME=skipper-python \
SKIPPER_CREDENTIALS_FILE=./service-account-skipper-bot.json \
make test
```

## Code Style

- Formatting and linting: `ruff` (run `make lint-fix` to auto-fix)
- Type checking: `mypy` in strict mode
- Python minimum: 3.10

## Pull Requests

- Ensure `make test`, `make lint`, and `make typecheck` all pass
- Add tests for new functionality
- Keep commits focused; one logical change per PR
