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
uv run cli.py sync ./your_docs
```

This shows a diff of changes and prompts for confirmation before applying.

### Cleanup

Delete all resources from OpenAI:

```bash
uv run cli.py cleanup
```

## How it works

1. `init` uploads your documents to OpenAI, creates a vector store, and sets up an assistant with file search capabilities.
2. `ask` sends your question to the assistant, which searches the vector store and returns an answer.
3. `sync` detects added/removed files and updates the vector store accordingly.
4. Config is stored locally in `.agentic_search_config.json`.

## License

MIT
