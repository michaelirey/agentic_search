#!/usr/bin/env python3
"""Agentic Search - CLI tool to search documents using OpenAI vector stores."""

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

import pathspec
from dotenv import load_dotenv

load_dotenv()

# Silence OpenAI Assistants API deprecation warnings (API works until Aug 2026)
warnings.filterwarnings("ignore", message=".*Assistants API is deprecated.*")

from openai import OpenAI

client = OpenAI()
CONFIG_FILE = ".agentic_search_config.json"
DEFAULT_INDEX_TIMEOUT = 300  # 5 minutes


def collect_files(folder: Path) -> list[Path]:
    """Recursively collect files from folder, respecting ignore rules.

    Respects .gitignore and .agentic_search_ignore files in the target folder.
    """
    folder = folder.resolve()

    # Load ignore patterns
    ignore_patterns = []

    # Read .gitignore
    gitignore_path = folder / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            ignore_patterns.extend(f.read().splitlines())

    # Read .agentic_search_ignore
    custom_ignore_path = folder / ".agentic_search_ignore"
    if custom_ignore_path.exists():
        with open(custom_ignore_path) as f:
            ignore_patterns.extend(f.read().splitlines())

    # Build pathspec (empty patterns match nothing)
    spec = pathspec.PathSpec.from_lines('gitwildmatch', ignore_patterns) if ignore_patterns else None

    # Recursively collect files
    files = []
    for root, dirs, filenames in os.walk(folder):
        root_path = Path(root)

        # Get relative path from folder
        try:
            rel_root = root_path.relative_to(folder)
        except ValueError:
            continue

        # Filter directories (modify in place to prune search)
        if spec:
            dirs[:] = [d for d in dirs if not spec.match_file(str(rel_root / d) + "/")]

        # Filter files
        for filename in filenames:
            file_path = root_path / filename
            rel_path = file_path.relative_to(folder)

            # Check if file should be ignored
            if not spec or not spec.match_file(str(rel_path)):
                files.append(file_path)

    return sorted(files)


def wait_for_indexing(vector_store_id: str, timeout: int = DEFAULT_INDEX_TIMEOUT) -> bool:
    """Wait for vector store indexing to complete with progress output.

    Args:
        vector_store_id: The vector store ID to monitor
        timeout: Maximum time to wait in seconds (default: 300)

    Returns:
        True if indexing completed successfully, False if timeout
    """
    print("Waiting for indexing...")
    start_time = time.time()
    sleep_time = 1  # Start with 1 second
    max_sleep = 10  # Cap at 10 seconds

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\nTimeout after {timeout}s. Indexing may still be in progress.")
            return False

        vs = client.vector_stores.retrieve(vector_store_id)
        completed = vs.file_counts.completed
        failed = vs.file_counts.failed
        in_progress = vs.file_counts.in_progress

        # Show progress
        print(f"  [{int(elapsed)}s] Completed: {completed}, Failed: {failed}, In Progress: {in_progress}")

        if in_progress == 0:
            if failed > 0:
                print(f"\nWarning: {failed} file(s) failed to index")
            return True

        # Sleep with exponential backoff
        time.sleep(sleep_time)
        sleep_time = min(sleep_time * 1.5, max_sleep)


def load_config():
    """Load config file or exit with error."""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: Not initialized. Run 'python cli.py init <folder>' first.")
        sys.exit(1)


def save_config(config):
    """Save config to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def cmd_init(args):
    """Initialize: upload documents and create vector store."""
    folder = Path(args.folder)

    if not folder.exists():
        print(f"Error: Folder '{args.folder}' does not exist.")
        sys.exit(1)

    # Check if already initialized
    if os.path.exists(CONFIG_FILE):
        response = input("Already initialized. Reinitialize? This will delete existing resources. [y/N] ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
        # Cleanup existing resources (skip confirmation)
        class CleanupArgs:
            yes = True
        cmd_cleanup(CleanupArgs())

    # Collect files recursively
    file_paths = collect_files(folder)

    if not file_paths:
        print("Error: No files found in folder.")
        sys.exit(1)

    print(f"Found {len(file_paths)} file(s) to index.")

    # Upload all files
    file_ids = []
    file_names = []
    file_id_map = {}  # relative path -> id mapping for sync

    for file_path in file_paths:
        rel_path = file_path.relative_to(folder)
        print(f"Uploading {rel_path}...")
        with open(file_path, "rb") as f:
            file = client.files.create(file=f, purpose="assistants")
        file_ids.append(file.id)
        file_names.append(str(rel_path))
        file_id_map[str(rel_path)] = file.id

    # Create vector store
    print("Creating vector store...")
    vector_store = client.vector_stores.create(
        name="agentic_search_docs",
        file_ids=file_ids
    )

    # Wait for indexing with progress
    wait_for_indexing(vector_store.id)

    # Create assistant
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

    # Save config
    config = {
        "assistant_id": assistant.id,
        "vector_store_id": vector_store.id,
        "file_ids": file_ids,
        "file_names": file_names,
        "file_id_map": file_id_map,
        "folder": str(folder.resolve())
    }
    save_config(config)

    print(f"\nDone! Indexed {len(file_ids)} documents.")


def cmd_ask(args):
    """Ask a question about the indexed documents."""
    config = load_config()

    doc_count = len(config.get("file_names", []))
    print(f"Searching {doc_count} document(s)...", file=sys.stderr)

    # Create thread and run
    thread = client.beta.threads.create(
        messages=[{"role": "user", "content": args.question}]
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=config["assistant_id"]
    )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        answer = messages.data[0].content[0].text.value
        print(answer)
    else:
        print(f"Error: Run failed with status {run.status}")
        sys.exit(1)


def cmd_list(args):
    """List indexed documents."""
    config = load_config()

    file_names = config.get("file_names", [])
    if not file_names:
        print("No documents indexed.")
        return

    print("Indexed documents:")
    for i, name in enumerate(file_names, 1):
        print(f"  {i}. {name}")


def cmd_stats(args):
    """Show statistics about the vector store."""
    config = load_config()

    vs = client.vector_stores.retrieve(config["vector_store_id"])

    print(f"Documents:      {len(config.get('file_names', []))}")
    print(f"Vector Store:   {vs.id}")
    print(f"Status:         {vs.status}")
    print(f"Storage:        {vs.usage_bytes:,} bytes")
    print(f"Files:          {vs.file_counts.completed} completed, {vs.file_counts.failed} failed, {vs.file_counts.in_progress} in progress")

    if config.get("folder"):
        print(f"Source folder:  {config['folder']}")


def cmd_sync(args):
    """Sync folder changes with vector store (nuke and pave approach)."""
    config = load_config()
    folder = Path(args.folder)

    if not folder.exists():
        print(f"Error: Folder '{args.folder}' does not exist.")
        sys.exit(1)

    # Get current files in folder (recursively)
    file_paths = collect_files(folder)
    current_files = {str(f.relative_to(folder)) for f in file_paths}
    indexed_files = set(config.get("file_names", []))

    # Calculate diff for display
    to_add = current_files - indexed_files
    to_remove = indexed_files - current_files
    unchanged = current_files & indexed_files

    # Show diff
    print(f"Unchanged: {len(unchanged)} file(s)")

    if to_add:
        print(f"\nTo add ({len(to_add)}):")
        for f in sorted(to_add):
            print(f"  + {f}")

    if to_remove:
        print(f"\nTo remove ({len(to_remove)}):")
        for f in sorted(to_remove):
            print(f"  - {f}")

    if not to_add and not to_remove:
        print("\nNo changes needed.")
        return

    # Prompt for confirmation
    if not getattr(args, 'yes', False):
        response = input("\nApply changes? (will re-upload all files) [y/N] ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    # NUKE: Delete all existing files from vector store
    print("\nRemoving all files from vector store...")
    for file_id in config.get("file_ids", []):
        try:
            client.vector_stores.files.delete(
                vector_store_id=config["vector_store_id"],
                file_id=file_id
            )
            client.files.delete(file_id)
        except Exception:
            pass

    # PAVE: Re-upload all files from folder
    print("Uploading files...")
    file_ids = []
    file_names = []
    file_id_map = {}
    for file_path in file_paths:
        rel_path = file_path.relative_to(folder)
        print(f"  {rel_path}")
        with open(file_path, "rb") as f:
            file = client.files.create(file=f, purpose="assistants")
        client.vector_stores.files.create(
            vector_store_id=config["vector_store_id"],
            file_id=file.id
        )
        file_ids.append(file.id)
        file_names.append(str(rel_path))
        file_id_map[str(rel_path)] = file.id

    # Wait for indexing with progress
    wait_for_indexing(config["vector_store_id"])

    # Update config
    config["file_ids"] = file_ids
    config["file_names"] = file_names
    config["file_id_map"] = file_id_map
    config["folder"] = str(folder.resolve())
    save_config(config)

    print(f"\nDone! Indexed {len(file_names)} document(s).")


def cmd_cleanup(args):
    """Delete all resources from OpenAI."""
    try:
        config = load_config()
    except SystemExit:
        print("Nothing to clean up.")
        return

    if not getattr(args, 'yes', False):
        response = input("Delete all resources? [y/N] ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    print("Deleting assistant...")
    try:
        client.beta.assistants.delete(config["assistant_id"])
    except Exception as e:
        print(f"  Warning: {e}")

    print("Deleting vector store...")
    try:
        client.vector_stores.delete(config["vector_store_id"])
    except Exception as e:
        print(f"  Warning: {e}")

    print("Deleting uploaded files...")
    for fid in config.get("file_ids", []):
        try:
            client.files.delete(fid)
        except Exception:
            pass

    os.remove(CONFIG_FILE)
    print("Cleaned up.")


def main():
    parser = argparse.ArgumentParser(
        prog="agentic-search",
        description="Search documents using OpenAI vector stores"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize with documents from a folder")
    init_parser.add_argument("folder", help="Folder containing documents")

    # ask
    ask_parser = subparsers.add_parser("ask", help="Ask a question about the documents")
    ask_parser.add_argument("question", help="Question to ask")

    # list
    subparsers.add_parser("list", help="List indexed documents")

    # stats
    subparsers.add_parser("stats", help="Show vector store statistics")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync folder changes (add/remove files)")
    sync_parser.add_argument("folder", help="Folder to sync")
    sync_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Delete all resources from OpenAI")
    cleanup_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "ask": cmd_ask,
        "list": cmd_list,
        "stats": cmd_stats,
        "sync": cmd_sync,
        "cleanup": cmd_cleanup,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
