#!/usr/bin/env python3
"""Ask a question about the indexed documents."""

import json
import sys
import warnings

# Silence OpenAI Assistants API deprecation warnings (API works until Aug 2026)
warnings.filterwarnings("ignore", message=".*Assistants API is deprecated.*")

from openai import OpenAI

client = OpenAI()  # Uses OPENAI_API_KEY from environment


def ask(question: str) -> None:
    # 1. Load config
    try:
        with open(".agentic_search_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: Run setup_docs.py first to index documents.")
        sys.exit(1)

    # Show doc count
    doc_count = len(config.get("file_names", config.get("file_ids", [])))
    print(f"Searching {doc_count} document(s)...", file=sys.stderr)

    # 2. Create thread with question
    thread = client.beta.threads.create(
        messages=[{"role": "user", "content": question}]
    )

    # 3. Run assistant (LLM CALL - searches docs + generates answer)
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=config["assistant_id"]
    )

    # 4. Get and print response
    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        answer = messages.data[0].content[0].text.value
        print(answer)
    else:
        print(f"Error: Run failed with status {run.status}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ask_docs.py \"Your question here\"")
        sys.exit(1)
    ask(sys.argv[1])
