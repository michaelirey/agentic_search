#!/usr/bin/env python3
"""Setup script: uploads documents and creates OpenAI assistant with vector store."""

import argparse
import json
from pathlib import Path

from openai import OpenAI

client = OpenAI()  # Uses OPENAI_API_KEY from environment


def setup(folder_path: str) -> None:
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Error: Folder '{folder_path}' does not exist.")
        return

    # 1. Upload all files
    file_ids = []
    file_names = []
    for file_path in folder.iterdir():
        if file_path.is_file():
            print(f"Uploading {file_path.name}...")
            with open(file_path, "rb") as f:
                file = client.files.create(file=f, purpose="assistants")
            file_ids.append(file.id)
            file_names.append(file_path.name)

    if not file_ids:
        print("Error: No files found in folder.")
        return

    # 2. Create vector store with files
    print("Creating vector store...")
    vector_store = client.vector_stores.create(
        name="agentic_search_docs",
        file_ids=file_ids
    )

    # 3. Wait for files to be indexed
    print("Waiting for files to be indexed...")
    while True:
        vs = client.vector_stores.retrieve(vector_store.id)
        if vs.file_counts.in_progress == 0:
            break

    # 4. Create assistant with system prompt
    print("Creating assistant...")
    assistant = client.beta.assistants.create(
        name="Doc Search Assistant",
        model="gpt-4o",
        instructions="""You are a helpful assistant that answers questions based on the provided documents.

When answering:
- Search the uploaded documents for relevant information
- Base your answer only on what you find in the documents
- If the answer isn't in the documents, say so
- Be concise and direct""",
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
    )

    # 5. Save config
    config = {
        "assistant_id": assistant.id,
        "vector_store_id": vector_store.id,
        "file_ids": file_ids,
        "file_names": file_names
    }
    with open(".agentic_search_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print(f"Done! Uploaded {len(file_ids)} files.")
    print("Config saved to .agentic_search_config.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup document search")
    parser.add_argument("--folder", required=True, help="Path to folder with documents")
    args = parser.parse_args()
    setup(args.folder)
