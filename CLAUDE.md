# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentic Search is a Python CLI tool that implements a Retrieval-Augmented Generation (RAG) system using OpenAI's vector stores and assistants. Users upload documents and ask natural language questions that are answered by searching through an indexed document collection.

## Commands

```bash
# Install dependencies
uv sync

# Install with test dependencies
uv sync --extra test

# Run CLI commands
uv run cli.py init ./docs
uv run cli.py ask "Your question"
uv run cli.py list
uv run cli.py stats
uv run cli.py sync ./docs
uv run cli.py cleanup

# Run tests
uv run python -m pytest -q
```

## Architecture

Single-file CLI application (`cli.py`, ~500 lines) with all functionality in one module.

**Core Flow:**
1. `init` - Recursively uploads documents from folder, creates OpenAI vector store and assistant, saves config to `.agentic_search_config.json`
2. `ask` - Creates ephemeral thread, runs assistant with file_search against vector store
3. `sync` - Compares folder vs indexed files, uses "nuke and pave" approach (deletes all, re-uploads)
4. `cleanup` - Deletes OpenAI resources (assistant, vector store, files) and local config

**Key Components:**
- `iter_document_files()` - Recursive file discovery with ignore rule support
- `build_ignore_specs()` - Combines default patterns, `.gitignore`, and `.agentic_search_ignore` rules
- `wait_for_indexing()` - Polls vector store with exponential backoff until indexing complete
- `get_client()` - Singleton OpenAI client (requires `OPENAI_API_KEY` env var)

**Ignore System:**
Files are filtered using gitignore-style patterns from multiple sources:
- Default: `.git/`, `.env`, `.agentic_search_config.json`
- Repository `.gitignore`
- Project `.agentic_search_ignore` (root and folder-level)

## Configuration

- Environment: Copy `.env.example` to `.env`, set `OPENAI_API_KEY`
- State: Stored in `.agentic_search_config.json` (assistant_id, vector_store_id, file mappings)
