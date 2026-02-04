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
uv run cli.py init ./your_docs
```

This recursively scans the folder and uploads all files. Supports: PDF, DOCX, TXT, MD, HTML, JSON, CSV, and code files.

**Ignore rules**: Files matching patterns in `.gitignore` or `.agentic_search_ignore` (at the folder root) are automatically excluded.

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

When you add or remove files from your folder (including nested subdirectories), sync the changes:

```bash
uv run cli.py sync ./your_docs
```

This recursively scans the folder, shows a diff of changes, and prompts for confirmation before applying. Uses the same ignore rules as `init`.

### Cleanup

Delete all resources from OpenAI:

```bash
uv run cli.py cleanup
```

## How it works

1. `init` recursively scans your folder (respecting ignore rules), uploads documents to OpenAI, creates a vector store, and sets up an assistant with file search capabilities.
2. `ask` sends your question to the assistant, which searches the vector store and returns an answer.
3. `sync` recursively scans and detects added/removed files, then updates the vector store accordingly.
4. Config is stored locally in `.agentic_search_config.json` (automatically git-ignored).

## Ignore rules

Both `init` and `sync` respect ignore patterns:
- `.gitignore` - Standard git ignore patterns
- `.agentic_search_ignore` - Custom ignore file (same format as .gitignore)

Place these files at the root of your document folder. Common patterns to ignore:
```
# Example .agentic_search_ignore
*.log
*.tmp
node_modules/
__pycache__/
.DS_Store
```

## License

MIT
