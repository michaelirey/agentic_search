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

This recursively scans the folder and uploads all files. Hidden files (starting with `.`) are automatically excluded.

**Options:**
- `--timeout SECONDS` - Max seconds to wait for indexing (default: 300, use 0 for no limit)

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

**Options:**
- `-y, --yes` - Skip confirmation prompt
- `--timeout SECONDS` - Max seconds to wait for indexing (default: 300, use 0 for no limit)

### Cleanup

Delete all resources from OpenAI:

```bash
uv run cli.py cleanup
```

## Ignore Rules

The tool respects ignore patterns to exclude files from ingestion:

### `.gitignore`

If your folder is inside a git repository, all `.gitignore` files from the folder up to the git root are respected.

### `.agentic_search_ignore`

You can create a `.agentic_search_ignore` file to specify additional patterns to exclude. This file uses the same syntax as `.gitignore`.

**Locations checked:**
1. Git repository root (if applicable)
2. Target folder

**Example `.agentic_search_ignore`:**
```
# Exclude large files
*.zip
*.tar.gz

# Exclude generated content
build/
dist/
node_modules/

# Exclude specific files
secrets.txt
draft-*.md
```

### Pattern Syntax

Patterns follow gitignore syntax:
- `*.log` - Match all .log files
- `build/` - Match directory named "build"
- `!important.log` - Negate a pattern (include even if previously excluded)
- `**/temp` - Match "temp" in any directory
- `doc/*.txt` - Match .txt files only in doc/ directory

## How it works

1. `init` recursively scans your folder for files (respecting ignore rules), uploads them to OpenAI, creates a vector store, and sets up an assistant with file search capabilities.
2. `ask` sends your question to the assistant, which searches the vector store and returns an answer.
3. `sync` detects added/removed files (recursively, with ignore rules) and updates the vector store accordingly.
4. Config is stored locally in `.agentic_search_config.json`.

### Indexing Progress

During `init` and `sync`, the tool displays indexing progress:
```
Waiting for files to be indexed...
  Progress: 5 completed, 0 failed, 3 in progress
  Progress: 8 completed, 0 failed, 0 in progress
```

If any files fail to index, a warning is displayed. You can adjust the timeout with `--timeout` or set `--timeout 0` to wait indefinitely.

## Configuration

Config is stored in `.agentic_search_config.json` (gitignored by default).

**Important:** Never commit `.env` or `.agentic_search_config.json` to version control.

## License

MIT
