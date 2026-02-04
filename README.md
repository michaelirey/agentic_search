# Agentic Search

A simple RAG (Retrieval-Augmented Generation) CLI tool that lets you ask natural language questions about your documents using OpenAI's vector stores.

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env with your OpenAI API key
```

## Usage

### Initialize with documents

```bash
uv run cli.py init ./your_docs [--timeout 600]
```

**New in v0.2.0:**
- **Recursive Ingestion:** Files in subfolders are now automatically included.
- **Ignore Rules:** Respects `.gitignore` and `.agentic_search_ignore`. Use `.agentic_search_ignore` at the repo root or in your target folder to exclude specific files or patterns.
- **Improved Indexing:** Safer wait loop with backoff, progress reporting, and configurable timeout.

Supports: PDF, DOCX, TXT, MD, HTML, JSON, CSV, and code files.

### Ask questions

```bash
uv run cli.py ask "What is the main topic of these documents?"
```

### List indexed documents

```bash
uv run cli.py list
```

### Show statistics

```bash
uv run cli.py stats
```

### Sync folder changes

When you add or remove files from your folder, sync the changes:

```bash
uv run cli.py sync ./your_docs [-y] [--timeout 600]
```

This shows a diff of changes and prompts for confirmation before applying. It also respects ignore rules and processes subfolders recursively.

### Cleanup

Delete all resources from OpenAI:

```bash
uv run cli.py cleanup
```

## How it works

1. `init` uploads your documents to OpenAI, creates a vector store, and sets up an assistant with file search capabilities. It recursively walks the target folder and filters files based on ignore rules.
2. `ask` sends your question to the assistant, which searches the vector store and returns an answer.
3. `sync` detects added/removed files and updates the vector store accordingly.
4. Config is stored locally in `.agentic_search_config.json`.

### Ignore Rules

By default, `.git`, `.env`, and `.agentic_search_config.json` are always ignored.
The tool also respects patterns found in:
1. `.gitignore` in the current working directory.
2. `.agentic_search_ignore` in the current working directory.
3. `.agentic_search_ignore` in the target documents folder.

## License

MIT
