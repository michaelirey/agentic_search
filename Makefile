.PHONY: help install format format-check lint test ci

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (test + lint extras)
	uv sync --extra test --extra lint

format: ## Format code with ruff
	uv run ruff format .

format-check: ## Check code formatting with ruff
	uv run ruff format --check .

lint: ## Run ruff linter
	uv run ruff check .

test: ## Run tests with pytest
	uv run python -m pytest -q

ci: format-check lint test ## Run all CI checks (format-check + lint + test)
