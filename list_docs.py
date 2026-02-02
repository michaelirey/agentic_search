#!/usr/bin/env python3
"""List all documents in the vector store."""

import json
import sys


def list_docs() -> None:
    try:
        with open(".agentic_search_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: Run setup_docs.py first to index documents.")
        sys.exit(1)

    file_names = config.get("file_names", [])

    if not file_names:
        print("No file names stored. Re-run setup_docs.py to update.")
        return

    print("Documents in vector store:")
    for i, name in enumerate(file_names, 1):
        print(f"  {i}. {name}")


if __name__ == "__main__":
    list_docs()
