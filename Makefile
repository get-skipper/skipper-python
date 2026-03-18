.PHONY: install test test-sync lint typecheck build clean

install:
	uv sync --all-packages

test:
	uv run pytest tests/ -p no:skipper -x

test-sync:
	SKIPPER_MODE=sync uv run pytest tests/ -p no:skipper -x

lint:
	uv run ruff check .
	uv run ruff format --check .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy \
		packages/skipper-core/src \
		packages/skipper-pytest/src \
		packages/skipper-unittest/src \
		packages/skipper-playwright/src

build:
	uv build --all-packages

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
