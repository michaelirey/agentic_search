# Agentic Search

A simple RAG (Retrieval-Augmented Generation) CLI tool that lets you ask natural language questions about your documents using OpenAI's vector stores.

## Quickstart

Get up and running in less than 5 minutes.

1.  **Install uv** (fast Python package manager):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Setup environment**:
    ```bash
    cp .env.example .env
    # Edit .env and add your OPENAI_API_KEY
    ```

3.  **Initialize with your documents**:
    ```bash
    uv run cli.py init ./your_docs_folder
    ```

4.  **Ask a question**:
    ```bash
    uv run cli.py ask "What is the summary of project X?"
    ```

## CLI Reference

Usage: `uv run cli.py <command> [args]`

| Command | Description | Example |
| :--- | :--- | :--- |
| `init` | Uploads docs & creates vector store | `init ./docs` |
| `ask` | Ask a question about indexed docs | `ask "How do I...?"` |
| `list` | List currently indexed files | `list` |
| `stats` | Show vector store usage & status | `stats` |
| `sync` | Sync folder changes (add/remove) | `sync ./docs` |
| `cleanup` | Delete all OpenAI resources & config | `cleanup` |

## Ignoring Files

To exclude files from indexing (e.g., secrets, large binaries), you can use:

1.  **`.gitignore`**: The CLI automatically respects your root `.gitignore`.
2.  **`.agentic_search_ignore`**: Create this file in your repo root or target folder to add specific ignore patterns (uses gitignore syntax).

**Note:** `.env` and `.agentic_search_config.json` are *always* ignored automatically to prevent leaking secrets.

## License

[MIT](LICENSE)