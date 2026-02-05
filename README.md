# Agentic Search

A simple RAG (Retrieval-Augmented Generation) CLI that lets you ask natural language questions about your documents using OpenAI vector stores.

**Quickstart (under 5 minutes)**

```bash
# 1) Install uv if you don't have it yet
python -m pip install uv

# 2) Install dependencies
uv sync

# 3) Configure your API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=...

# 4) Index a folder of documents
uv run cli.py init ./docs

# 5) Ask a question
uv run cli.py ask "What is the main topic of these documents?"
```

## CLI usage

Check the installed version:

```bash
uv run cli.py --version
```

Initialize with documents:

```bash
uv run cli.py init ./docs
```

Optional flags:

```bash
uv run cli.py init ./docs --index-timeout 900
```

Ask a question:

```bash
uv run cli.py ask "Summarize the key themes."
```

List indexed documents:

```bash
uv run cli.py list
```

Show statistics:

```bash
uv run cli.py stats
```

Sync folder changes (add/remove files):

```bash
uv run cli.py sync ./docs
```

Optional flags:

```bash
uv run cli.py sync ./docs --index-timeout 900
uv run cli.py sync ./docs --yes
```

Cleanup (delete all OpenAI resources for this project):

```bash
uv run cli.py cleanup
```

Optional flags:

```bash
uv run cli.py cleanup --yes
```

## Supported documents

Documents are ingested recursively. Supported file types include PDF, DOCX, TXT, MD, HTML, JSON, CSV, and common code files.

## Ignore rules and secrets

The CLI respects `.gitignore` at the repo root (if present). You can also create a `.agentic_search_ignore` file either at the repo root or inside the target folder; if both exist, both are applied. Patterns use gitignore-style matching.

`.env` and `.agentic_search_config.json` are always ignored.

To exclude secrets, keep them out of your docs folder and add patterns to `.agentic_search_ignore`. Example:

```gitignore
# Secrets and keys
**/*.pem
**/*.key
secrets/
```

## How it works

1. `init` uploads your documents to OpenAI, creates a vector store, and sets up an assistant with file search capabilities.
2. `ask` sends your question to the assistant, which searches the vector store and returns an answer.
3. `sync` detects added/removed files and updates the vector store accordingly.
4. Config is stored locally in `.agentic_search_config.json`.

## Testing

Install the test dependencies:

```bash
uv sync --extra test
```

Run the test suite:

```bash
uv run python -m pytest -q
```

## Linting

Install the lint dependencies:

```bash
uv sync --extra lint
```

Check formatting:

```bash
uv run ruff format --check .
```

Auto-fix formatting:

```bash
uv run ruff format .
```

Run linter:

```bash
uv run ruff check .
```

## Type checking

Install the lint dependencies:

```bash
uv sync --extra lint
```

Run type checker:

```bash
uv run mypy .
```

## Makefile shortcuts

Optional `make` targets that wrap the commands above:

```bash
make install
make format
make format-check
make lint
make test
make ci
```

## License

MIT. See [LICENSE](LICENSE).
