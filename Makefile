.DEFAULT_GOAL := help
.PHONY: help install format format-check lint test ci

help:
	@echo "Available targets:"
	@echo "  make install       Install dependencies with uv (includes all extras for dev)"
	@echo "  make format        Format code with ruff"
	@echo "  make format-check  Check code formatting with ruff"
	@echo "  make lint          Lint code with ruff"
	@echo "  make test          Run tests with pytest"
	@echo "  make ci            Run all checks (format-check, lint, test in order)"

# Installs all extras for local development (CI installs lint/test separately)
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
