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

_client = None
CONFIG_FILE = ".agentic_search_config.json"


def get_client() -> OpenAI:
    """Get OpenAI client (lazy-loaded)."""
    global _client
    if _client is None:
        _client = OpenAI()
    return _client

# Default indexing timeout in seconds
DEFAULT_INDEXING_TIMEOUT = 300  # 5 minutes


def load_ignore_patterns(folder: Path) -> pathspec.PathSpec:
    """Load ignore patterns from .gitignore and .agentic_search_ignore files.

    Searches for ignore files in:
    1. The target folder
    2. Parent directories up to git root (for .gitignore)
    3. Git root (for .agentic_search_ignore)
    """
    patterns = []

    # Find git root by looking for .git directory
    git_root = None
    current = folder.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            git_root = current
            break
        current = current.parent

    # Collect .gitignore files from folder up to git root
    if git_root:
        current = folder.resolve()
        gitignore_files = []
        while current != git_root.parent:
            gitignore = current / ".gitignore"
            if gitignore.exists():
                gitignore_files.append(gitignore)
            current = current.parent

        # Process gitignores from root to leaf for proper precedence
        for gitignore in reversed(gitignore_files):
            try:
                patterns.extend(gitignore.read_text().splitlines())
            except Exception:
                pass

    # Check for .gitignore in target folder if no git root
    elif (folder / ".gitignore").exists():
        try:
            patterns.extend((folder / ".gitignore").read_text().splitlines())
        except Exception:
            pass

    # Check for .agentic_search_ignore in git root and target folder
    ignore_locations = [folder]
    if git_root and git_root != folder:
        ignore_locations.insert(0, git_root)

    for location in ignore_locations:
        ignore_file = location / ".agentic_search_ignore"
        if ignore_file.exists():
            try:
                patterns.extend(ignore_file.read_text().splitlines())
            except Exception:
                pass

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def discover_files(folder: Path, ignore_spec: pathspec.PathSpec) -> list[Path]:
    """Recursively discover files in folder, respecting ignore patterns.

    Returns a sorted list of file paths relative to the folder.
    """
    folder = folder.resolve()
    files = []

    for file_path in folder.rglob("*"):
        if not file_path.is_file():
            continue

        # Get path relative to folder for matching
        try:
            rel_path = file_path.relative_to(folder)
        except ValueError:
            continue

        # Skip hidden files and directories (starting with .)
        if any(part.startswith(".") for part in rel_path.parts):
            continue

        # Check against ignore patterns
        if ignore_spec.match_file(str(rel_path)):
            continue

        files.append(file_path)

    return sorted(files)


def wait_for_indexing(vector_store_id: str, timeout: int = DEFAULT_INDEXING_TIMEOUT) -> bool:
    """Wait for vector store indexing with exponential backoff and progress.

    Args:
        vector_store_id: The vector store ID to monitor
        timeout: Maximum seconds to wait (0 = no limit)

    Returns:
        True if indexing completed successfully, False if timeout or all failed
    """
    print("Waiting for files to be indexed...")

    start_time = time.time()
    poll_interval = 1.0  # Start with 1 second
    max_interval = 10.0  # Cap at 10 seconds
    last_status = None

    while True:
        vs = get_client().vector_stores.retrieve(vector_store_id)
        counts = vs.file_counts

        # Build status string
        status = f"  Progress: {counts.completed} completed, {counts.failed} failed, {counts.in_progress} in progress"

        # Only print if status changed
        if status != last_status:
            print(status)
            last_status = status

        # Check if done
        if counts.in_progress == 0:
            if counts.failed > 0:
                print(f"  Warning: {counts.failed} file(s) failed to index")
            return counts.completed > 0 or counts.failed == 0

        # Check timeout
        if timeout > 0:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(f"  Error: Indexing timed out after {timeout} seconds")
                return False

        # Wait with exponential backoff
        time.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.5, max_interval)


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
    timeout = getattr(args, 'timeout', DEFAULT_INDEXING_TIMEOUT)

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

    # Load ignore patterns
    ignore_spec = load_ignore_patterns(folder)

    # Discover files recursively
    print(f"Scanning {folder} for files...")
    files_to_upload = discover_files(folder, ignore_spec)

    if not files_to_upload:
        print("Error: No files found in folder (after applying ignore rules).")
        sys.exit(1)

    print(f"Found {len(files_to_upload)} file(s) to upload")

    # Upload all files
    file_ids = []
    file_names = []
    file_id_map = {}  # relative path -> id mapping for sync

    for file_path in files_to_upload:
        rel_path = file_path.relative_to(folder.resolve())
        print(f"Uploading {rel_path}...")
        with open(file_path, "rb") as f:
            file = get_client().files.create(file=f, purpose="assistants")
        file_ids.append(file.id)
        file_names.append(str(rel_path))
        file_id_map[str(rel_path)] = file.id

    # Create vector store
    print("Creating vector store...")
    vector_store = get_client().vector_stores.create(
        name="agentic_search_docs",
        file_ids=file_ids
    )

    # Wait for indexing
    if not wait_for_indexing(vector_store.id, timeout):
        print("Error: Indexing did not complete successfully.")
        sys.exit(1)

    # Create assistant
    print("Creating assistant...")
    assistant = get_client().beta.assistants.create(
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

    print(f"\nDone! Indexed {len(file_ids)} document(s).")


def cmd_ask(args):
    """Ask a question about the indexed documents."""
    config = load_config()

    doc_count = len(config.get("file_names", []))
    print(f"Searching {doc_count} document(s)...", file=sys.stderr)

    # Create thread and run
    thread = get_client().beta.threads.create(
        messages=[{"role": "user", "content": args.question}]
    )

    run = get_client().beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=config["assistant_id"]
    )

    if run.status == "completed":
        messages = get_client().beta.threads.messages.list(thread_id=thread.id)
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

    vs = get_client().vector_stores.retrieve(config["vector_store_id"])

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
    timeout = getattr(args, 'timeout', DEFAULT_INDEXING_TIMEOUT)

    if not folder.exists():
        print(f"Error: Folder '{args.folder}' does not exist.")
        sys.exit(1)

    # Load ignore patterns and discover files recursively
    ignore_spec = load_ignore_patterns(folder)
    files_to_upload = discover_files(folder, ignore_spec)

    # Get current files (as relative paths)
    current_files = {str(f.relative_to(folder.resolve())) for f in files_to_upload}
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
            get_client().vector_stores.files.delete(
                vector_store_id=config["vector_store_id"],
                file_id=file_id
            )
            get_client().files.delete(file_id)
        except Exception:
            pass

    # PAVE: Re-upload all files from folder
    print("Uploading files...")
    file_ids = []
    file_names = []
    file_id_map = {}
    for file_path in files_to_upload:
        rel_path = file_path.relative_to(folder.resolve())
        print(f"  {rel_path}")
        with open(file_path, "rb") as f:
            file = get_client().files.create(file=f, purpose="assistants")
        get_client().vector_stores.files.create(
            vector_store_id=config["vector_store_id"],
            file_id=file.id
        )
        file_ids.append(file.id)
        file_names.append(str(rel_path))
        file_id_map[str(rel_path)] = file.id

    # Wait for indexing
    if not wait_for_indexing(config["vector_store_id"], timeout):
        print("Warning: Indexing did not complete successfully.")

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
        get_client().beta.assistants.delete(config["assistant_id"])
    except Exception as e:
        print(f"  Warning: {e}")

    print("Deleting vector store...")
    try:
        get_client().vector_stores.delete(config["vector_store_id"])
    except Exception as e:
        print(f"  Warning: {e}")

    print("Deleting uploaded files...")
    for fid in config.get("file_ids", []):
        try:
            get_client().files.delete(fid)
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
    init_parser.add_argument("folder", help="Folder containing documents (scanned recursively)")
    init_parser.add_argument(
        "--timeout", type=int, default=DEFAULT_INDEXING_TIMEOUT,
        help=f"Max seconds to wait for indexing (default: {DEFAULT_INDEXING_TIMEOUT}, 0=no limit)"
    )

    # ask
    ask_parser = subparsers.add_parser("ask", help="Ask a question about the documents")
    ask_parser.add_argument("question", help="Question to ask")

    # list
    subparsers.add_parser("list", help="List indexed documents")

    # stats
    subparsers.add_parser("stats", help="Show vector store statistics")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync folder changes (add/remove files)")
    sync_parser.add_argument("folder", help="Folder to sync (scanned recursively)")
    sync_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    sync_parser.add_argument(
        "--timeout", type=int, default=DEFAULT_INDEXING_TIMEOUT,
        help=f"Max seconds to wait for indexing (default: {DEFAULT_INDEXING_TIMEOUT}, 0=no limit)"
    )

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
