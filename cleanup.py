#!/usr/bin/env python3
"""Cleanup: deletes assistant, vector store, and uploaded files from OpenAI."""

import json
import os
import sys

from openai import OpenAI

client = OpenAI()  # Uses OPENAI_API_KEY from environment


def cleanup() -> None:
    try:
        with open(".agentic_search_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: No config file found. Nothing to clean up.")
        sys.exit(1)

    print("Deleting assistant...")
    client.beta.assistants.delete(config["assistant_id"])

    print("Deleting vector store...")
    client.vector_stores.delete(config["vector_store_id"])

    print("Deleting uploaded files...")
    for fid in config["file_ids"]:
        client.files.delete(fid)

    os.remove(".agentic_search_config.json")
    print("Cleaned up.")


if __name__ == "__main__":
    cleanup()
