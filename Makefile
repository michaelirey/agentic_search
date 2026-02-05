.PHONY: help install format format-check lint test ci

help:
	@echo "Available targets:"
	@echo "  make install       Install dependencies with uv (including extras)"
	@echo "  make format        Format code with ruff"
	@echo "  make format-check  Check code formatting with ruff"
	@echo "  make lint          Lint code with ruff"
	@echo "  make test          Run tests with pytest"
	@echo "  make ci            Run all checks (format-check, lint, test)"

install:
	uv sync --all-extras

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

test:
	uv run python -m pytest -q

ci: format-check lint test
