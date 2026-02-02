# Agentic Search

A simple RAG (Retrieval-Augmented Generation) tool that lets you ask natural language questions about your documents using OpenAI's vector stores.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
```

## Usage

### 1. Index your documents

```bash
python setup_docs.py --folder ./your_docs
```

Supports: PDF, DOCX, TXT, MD, HTML, JSON, CSV, and code files.

### 2. Ask questions

```bash
python ask_docs.py "What is the main topic of these documents?"
```

### 3. List indexed documents

```bash
python list_docs.py
```

### 4. Cleanup (when done)

```bash
python cleanup.py
```

## How it works

1. `setup_docs.py` uploads your documents to OpenAI, creates a vector store, and sets up an assistant with file search capabilities.
2. `ask_docs.py` sends your question to the assistant, which searches the vector store and returns an answer.
3. Config is stored locally in `.agentic_search_config.json`.

## License

MIT
