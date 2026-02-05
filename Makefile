SHELL := /bin/sh
UV ?= uv

.PHONY: help install format format-check lint test ci

help: ## Show available targets
	@printf "Targets:\n"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dev dependencies (lint + test)
	$(UV) sync --extra lint --extra test

format: ## Auto-format code with ruff
	$(UV) run ruff format .

format-check: ## Check formatting with ruff
	$(UV) run ruff format --check .

lint: ## Run ruff lint checks
	$(UV) run ruff check .

test: ## Run pytest suite
	$(UV) run python -m pytest -q

ci: install format-check lint test ## Install deps, then run format-check, lint, and test (CI parity)
