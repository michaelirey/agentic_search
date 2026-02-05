#!/usr/bin/env python3
"""Agentic Search - CLI tool to search documents using OpenAI vector stores."""

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

# Try to import importlib.metadata for version detection
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    # Fallback for older python or if importlib is missing (unlikely in >=3.10)
    version = None
    PackageNotFoundError = None

from dotenv import load_dotenv
from pathspec import PathSpec

load_dotenv()

# Silence OpenAI Assistants API deprecation warnings (API works until Aug 2026)
warnings.filterwarnings("ignore", message=".*Assistants API is deprecated.*")

from openai import OpenAI

_client: OpenAI | None = None


def get_project_version() -> str:
    """Get project version from package metadata or pyproject.toml."""
    # 1. Try installed package metadata
    if version:
        try:
            return version("agentic-search")
        except PackageNotFoundError:
            pass

    # 2. Try reading pyproject.toml
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("version ="):
                        # Extract version from: version = "0.1.0"
                        return line.split("=")[1].strip().strip('"\'')
    except Exception:
        pass

    return "unknown"


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client
CONFIG_FILE = ".agentic_search_config.json"
DEFAULT_INDEX_TIMEOUT_SECONDS = 600
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
MAX_POLL_INTERVAL_SECONDS = 10.0


def find_repo_root(start: Path) -> Path | None:
    """Find the git repo root by walking up from start."""
    for candidate in [start] + list(start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def load_ignore_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text().splitlines()


def build_ignore_specs(folder: Path) -> list[tuple[PathSpec, Path]]:
    specs: list[tuple[PathSpec, Path]] = []
    repo_root = find_repo_root(folder)

    default_patterns = [
        ".git/",
        ".env",
        ".agentic_search_ignore",
        ".agentic_search_config.json",
    ]

    specs.append((PathSpec.from_lines("gitwildmatch", default_patterns), folder))
    if repo_root:
        specs.append((PathSpec.from_lines("gitwildmatch", default_patterns), repo_root))

    if repo_root:
        gitignore_path = repo_root / ".gitignore"
        gitignore_lines = load_ignore_lines(gitignore_path)
        if gitignore_lines:
            specs.append((PathSpec.from_lines("gitwildmatch", gitignore_lines), repo_root))

        root_ignore_path = repo_root / ".agentic_search_ignore"
        root_ignore_lines = load_ignore_lines(root_ignore_path)
        if root_ignore_lines:
            specs.append((PathSpec.from_lines("gitwildmatch", root_ignore_lines), repo_root))

    folder_ignore_path = folder / ".agentic_search_ignore"
    folder_ignore_lines = load_ignore_lines(folder_ignore_path)
    if folder_ignore_lines:
        specs.append((PathSpec.from_lines("gitwildmatch", folder_ignore_lines), folder))

    return specs


def is_ignored(path: Path, specs: list[tuple[PathSpec, Path]]) -> bool:
    for spec, base in specs:
        try:
            rel_path = path.relative_to(base)
            candidate = rel_path.as_posix()
        except ValueError:
            candidate = path.as_posix()
        if spec.match_file(candidate):
            return True
    return False


def iter_document_files(folder: Path) -> list[tuple[str, Path]]:
    specs = build_ignore_specs(folder)
    entries: list[tuple[str, Path]] = []
    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue
        if is_ignored(file_path, specs):
            continue
        rel_path = file_path.relative_to(folder).as_posix()
        entries.append((rel_path, file_path))
    return entries


def wait_for_indexing(vector_store_id: str, timeout_seconds: int, client: OpenAI) -> None:
    start_time = time.monotonic()
    poll_interval = DEFAULT_POLL_INTERVAL_SECONDS

    while True:
        vs = client.vector_stores.retrieve(vector_store_id)
        counts = vs.file_counts
        print(
            "Indexing status: "
            f"{counts.completed} completed, "
            f"{counts.failed} failed, "
            f"{counts.in_progress} in progress"
        )

        if counts.in_progress == 0:
            return

        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_seconds:
            print(f"Error: Indexing timed out after {int(elapsed)}s.")
            sys.exit(1)

        time.sleep(poll_interval)
        poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL_SECONDS)


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
    client = get_client()
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

    # Upload all files (recursive)
    file_ids = []
    file_names = []
    file_id_map = {}  # relative path -> id mapping for sync

    documents = iter_document_files(folder)
    for rel_path, file_path in documents:
        print(f"Uploading {rel_path}...")
        with open(file_path, "rb") as f:
            file = client.files.create(file=f, purpose="assistants")
        file_ids.append(file.id)
        file_names.append(rel_path)
        file_id_map[rel_path] = file.id

    if not file_ids:
        print("Error: No files found in folder.")
        sys.exit(1)

    # Create vector store
    print("Creating vector store...")
    vector_store = client.vector_stores.create(
        name="agentic_search_docs",
        file_ids=file_ids
    )

    # Wait for indexing
    print("Waiting for files to be indexed...")
    wait_for_indexing(vector_store.id, args.index_timeout, client)

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
    client = get_client()
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
    client = get_client()
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
    client = get_client()
    config = load_config()
    folder = Path(args.folder)

    if not folder.exists():
        print(f"Error: Folder '{args.folder}' does not exist.")
        sys.exit(1)

    # Get current files in folder
    documents = iter_document_files(folder)
    current_files = {rel_path for rel_path, _ in documents}
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
    for rel_path, file_path in sorted(documents, key=lambda item: item[0]):
        print(f"  {rel_path}")
        with open(file_path, "rb") as f:
            file = client.files.create(file=f, purpose="assistants")
        client.vector_stores.files.create(
            vector_store_id=config["vector_store_id"],
            file_id=file.id
        )
        file_ids.append(file.id)
        file_names.append(rel_path)
        file_id_map[rel_path] = file.id

    # Wait for indexing
    print("Waiting for indexing...")
    wait_for_indexing(config["vector_store_id"], args.index_timeout, client)

    # Update config
    config["file_ids"] = file_ids
    config["file_names"] = file_names
    config["file_id_map"] = file_id_map
    config["folder"] = str(folder.resolve())
    save_config(config)

    print(f"\nDone! Indexed {len(file_names)} document(s).")


def cmd_cleanup(args):
    """Delete all resources from OpenAI."""
    client = get_client()
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
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_project_version()}",
        help="Show version and exit"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize with documents from a folder")
    init_parser.add_argument("folder", help="Folder containing documents")
    init_parser.add_argument(
        "--index-timeout",
        type=int,
        default=DEFAULT_INDEX_TIMEOUT_SECONDS,
        help=f"Max seconds to wait for indexing (default: {DEFAULT_INDEX_TIMEOUT_SECONDS})",
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
    sync_parser.add_argument("folder", help="Folder to sync")
    sync_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    sync_parser.add_argument(
        "--index-timeout",
        type=int,
        default=DEFAULT_INDEX_TIMEOUT_SECONDS,
        help=f"Max seconds to wait for indexing (default: {DEFAULT_INDEX_TIMEOUT_SECONDS})",
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
