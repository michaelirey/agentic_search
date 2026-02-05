# Agentic Search

A CLI tool for asking natural language questions about your documents using OpenAI's vector stores.

## Quickstart

1. **Install [uv](https://docs.astral.sh/uv/getting-started/installation/)** (if you don't have it):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and set up**:
   ```bash
   git clone https://github.com/michaelirey/agentic_search.git
   cd agentic_search
   uv sync
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Index your documents**:
   ```bash
   uv run cli.py init ./your_docs
   ```

4. **Ask a question**:
   ```bash
   uv run cli.py ask "What is the main topic of these documents?"
   ```

## CLI Commands

| Command | Description |
|---------|-------------|
| `init <folder>` | Index documents from a folder |
| `ask "<question>"` | Ask a question about your documents |
| `list` | List all indexed documents |
| `stats` | Show vector store statistics |
| `sync <folder>` | Sync changes (add/remove files) |
| `cleanup` | Delete all resources from OpenAI |

### init

Upload and index documents from a folder:

```bash
uv run cli.py init ./docs
uv run cli.py init ./docs --index-timeout 900  # custom timeout (default: 600s)
```

Supported formats: PDF, DOCX, TXT, MD, HTML, JSON, CSV, and code files.

### ask

Ask a question about your indexed documents:

```bash
uv run cli.py ask "What are the key findings?"
uv run cli.py ask "Summarize the project requirements"
```

### list

Show all indexed documents:

```bash
uv run cli.py list
```

### stats

Display vector store statistics:

```bash
uv run cli.py stats
```

### sync

Sync folder changes with the vector store:

```bash
uv run cli.py sync ./docs
uv run cli.py sync ./docs -y                   # skip confirmation
uv run cli.py sync ./docs --index-timeout 900  # custom timeout
```

Shows a diff of added/removed files and prompts before applying changes.

### cleanup

Delete all OpenAI resources (assistant, vector store, files):

```bash
uv run cli.py cleanup
uv run cli.py cleanup -y  # skip confirmation
```

## Ignore Rules

Control which files are indexed using ignore files with gitignore-style patterns.

### How it works

1. `.gitignore` at the repo root is respected (if present)
2. `.agentic_search_ignore` can be placed at the repo root or inside the target folder
3. If both locations have `.agentic_search_ignore`, both are applied

### Always ignored

These files are always excluded from indexing:
- `.env`
- `.agentic_search_config.json`
- `.git/` directory

### Example `.agentic_search_ignore`

```gitignore
# Exclude build artifacts
build/
dist/
*.pyc

# Exclude secrets and credentials
*.pem
*credentials*
secrets/
```

## How It Works

1. **init** uploads your documents to OpenAI, creates a vector store, and sets up an assistant with file search capabilities
2. **ask** sends your question to the assistant, which searches the vector store and returns an answer
3. **sync** detects added/removed files and updates the vector store accordingly
4. Configuration is stored locally in `.agentic_search_config.json`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
