SHELL := /bin/sh
UV ?= uv

.PHONY: help install format format-check lint test typecheck ci

help: ## Show available targets
	@printf "Targets:\n"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dev dependencies (lint + test + typecheck)
	$(UV) sync --extra lint --extra test --extra typecheck

format: ## Auto-format code with ruff
	$(UV) run ruff format .

format-check: ## Check formatting with ruff
	$(UV) run ruff format --check .

lint: ## Run ruff lint checks
	$(UV) run ruff check .

test: ## Run pytest suite with coverage
	$(UV) run python -m pytest

typecheck: ## Run mypy type checks
	$(UV) run mypy

ci: install format-check lint test typecheck ## Install deps, then run format-check, lint, test, and typecheck (CI parity)
