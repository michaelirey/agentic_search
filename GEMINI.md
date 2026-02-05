# Agentic Search Context

This project is a Python-based CLI tool that implements a Retrieval-Augmented Generation (RAG) system using OpenAI's Assistants API and Vector Stores.

## Project Overview

*   **Purpose:** Allows users to index a directory of documents and ask natural language questions about their content.
*   **Main Technologies:**
    *   **Python (>=3.10):** Core language.
    *   **OpenAI Assistants API:** Used for managing vector stores, file search, and generating answers.
    *   **uv:** Fast Python package manager used for dependency and environment management.
    *   **pathspec:** Used for implementing `.gitignore`-style file exclusion rules.
*   **Architecture:**
    *   `cli.py`: Single-file CLI implementation using `argparse`.
    *   `.agentic_search_config.json`: Local storage for OpenAI resource IDs (Assistant, Vector Store, Files).
    *   `.env`: Environment file for the `OPENAI_API_KEY`.

## Building and Running

### Prerequisites
*   Python 3.10+
*   `uv` (Install via `python -m pip install uv`)
*   OpenAI API Key

### Setup
```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

### Key Commands
*   **Initialize:** `uv run cli.py init ./docs` (Uploads documents and creates an assistant)
*   **Ask Question:** `uv run cli.py ask "Your question here"`
*   **Sync Changes:** `uv run cli.py sync ./docs` (Updates the index when files change)
*   **Check Stats:** `uv run cli.py stats`
*   **List Files:** `uv run cli.py list`
*   **Cleanup:** `uv run cli.py cleanup` (Deletes all resources from OpenAI)

### Testing
```bash
# Run all tests
uv run pytest
```

## Development Conventions

*   **Dependency Management:** Always use `uv`. Add new dependencies with `uv add <package>`.
*   **OpenAI API:** The project uses the Assistants API (v2). It silences deprecation warnings for the Assistants API as it remains functional for now.
*   **Ignore Logic:** Follows gitignore patterns. Supports both `.gitignore` and project-specific `.agentic_search_ignore` files.
*   **Configuration:** All state is persisted in `.agentic_search_config.json`. Avoid manually editing this file.
*   **CLI Structure:** Commands are organized into functions prefixed with `cmd_` and dispatched from `main()`.
*   **Testing:** Tests are located in the `tests/` directory and use `pytest`. New features should include corresponding test cases in `tests/test_cli.py`.
