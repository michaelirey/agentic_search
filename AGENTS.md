# Repository Guidelines

## Project Structure & Module Organization
- `cli.py`: Single-file CLI implementation (argparse entrypoint + OpenAI integration).
- `tests/`: Pytest suite, currently `tests/test_cli.py` for CLI and helper functions.
- `pyproject.toml`: Project metadata, dependencies, and CLI entry point (`agentic-search`).
- `README.md`: Usage and workflow documentation.
- `uv.lock`: Locked dependency graph for `uv`.

## Build, Test, and Development Commands
- `uv sync`: Install dependencies from `pyproject.toml` and lockfile.
- `uv run cli.py --help`: Verify CLI wiring and available subcommands.
- `uv run cli.py init ./docs`: Index a document folder (creates `.agentic_search_config.json`).
- `uv run cli.py ask "..."`: Query indexed documents.
- `uv run cli.py sync ./docs`: Reconcile folder changes with the vector store.
- `uv run cli.py cleanup --yes`: Delete remote resources and local config.
- `uv run python -m pytest`: Run the test suite (pytest is in the `test` optional dependency).

## Coding Style & Naming Conventions
- Python, 4-space indentation, standard library first, then third-party imports.
- Functions and variables use `snake_case`; constants are `UPPER_SNAKE_CASE`.
- Files are lower case; tests are named `test_*.py` and functions `test_*`.
- No formatter/linter is configured; keep changes small and consistent with existing style.

## Testing Guidelines
- Framework: pytest.
- Tests live in `tests/` and mirror public behaviors and helper utilities in `cli.py`.
- Run all tests with `uv run python -m pytest` before submitting changes.

## Commit & Pull Request Guidelines
- Commit messages follow a concise “Topic: summary (#NN)” pattern, e.g. `Docs: update README (#26)`.
- For PRs, include a short summary, testing notes (commands run), and any relevant screenshots or CLI output when behavior changes.

## Security & Configuration Tips
- API keys are loaded from `.env`; never commit secrets.
- The CLI writes `.agentic_search_config.json` with IDs and local paths; keep it out of version control.
- Ignore rules: `.gitignore` and `.agentic_search_ignore` are respected for document ingestion.
