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
IGNORE_FILE = ".agentic_search_ignore"


def load_ignore_spec(folder):
    """Load ignore patterns from .gitignore and .agentic_search_ignore."""
    patterns = [
        ".git/",
        ".env",
        CONFIG_FILE,
        IGNORE_FILE,
        "__pycache__/",
        "*.pyc",
    ]

    # Load .gitignore
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            patterns.extend(f.readlines())

    # Load .agentic_search_ignore from repo root or target folder
    for p in [Path(IGNORE_FILE), folder / IGNORE_FILE]:
        if p.exists():
            with open(p) as f:
                patterns.extend(f.readlines())

    # Clean up patterns (remove empty lines and strip whitespace)
    cleaned_patterns = [p.strip() for p in patterns if p.strip() and not p.startswith("#")]

    return pathspec.PathSpec.from_lines("gitwildmatch", cleaned_patterns)


def get_files_to_index(folder):
    """Recursively find files in folder, respecting ignore rules."""
    spec = load_ignore_spec(folder)
    files = []
    
    cwd = Path.cwd().resolve()
    
    for root, dirs, filenames in os.walk(folder):
        root_path = Path(root).resolve()
        
        # Filter directories in-place for os.walk to avoid traversing ignored dirs
        filtered_dirs = []
        for d in dirs:
            dir_path = root_path / d
            try:
                rel_path = str(dir_path.relative_to(cwd))
            except ValueError:
                rel_path = str(dir_path)
            
            if not spec.match_file(rel_path + "/"):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs
        
        for filename in filenames:
            file_path = (root_path / filename).resolve()
            try:
                rel_path = str(file_path.relative_to(cwd))
            except ValueError:
                rel_path = str(file_path)
                
            if not spec.match_file(rel_path):
                files.append(file_path)
    
    return sorted(files)


def wait_for_indexing(vector_store_id, timeout=600):
    """Wait for files in the vector store to be indexed with backoff and timeout."""
    start_time = time.time()
    delay = 1
    max_delay = 10

    print("Waiting for files to be indexed...")
    while True:
        vs = client.vector_stores.retrieve(vector_store_id)
        counts = vs.file_counts
        
        total = counts.completed + counts.failed + counts.in_progress
        print(f"  Progress: {counts.completed} completed, {counts.failed} failed, {counts.in_progress} in progress (Total: {total})")
        
        if counts.in_progress == 0:
            if counts.failed > 0:
                print(f"  Warning: {counts.failed} files failed to index.")
            break
            
        if time.time() - start_time > timeout:
            print(f"  Error: Indexing timed out after {timeout} seconds.")
            sys.exit(1)
            
        time.sleep(delay)
        delay = min(delay * 1.5, max_delay)


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
    folder = Path(args.folder).resolve()

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

    # Find all files recursively
    files_to_upload = get_files_to_index(folder)
    
    if not files_to_upload:
        print(f"Error: No matching files found in {folder}")
        sys.exit(1)

    print(f"Found {len(files_to_upload)} files to index.")

    # Upload all files
    file_ids = []
    file_names = []  # These will be relative paths for clarity
    file_id_map = {}  # relative_path -> id mapping for sync

    for file_path in files_to_upload:
        rel_path = str(file_path.relative_to(folder))
        print(f"Uploading {rel_path}...")
        try:
            with open(file_path, "rb") as f:
                file = client.files.create(file=f, purpose="assistants")
            file_ids.append(file.id)
            file_names.append(rel_path)
            file_id_map[rel_path] = file.id
        except Exception as e:
            print(f"  Error uploading {rel_path}: {e}")

    if not file_ids:
        print("Error: Failed to upload any files.")
        sys.exit(1)

    # Create vector store
    print("Creating vector store...")
    vector_store = client.vector_stores.create(
        name="agentic_search_docs",
        file_ids=file_ids
    )

    # Wait for indexing
    wait_for_indexing(vector_store.id, timeout=args.timeout)

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
        "folder": str(folder)
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
    folder = Path(args.folder).resolve()

    if not folder.exists():
        print(f"Error: Folder '{args.folder}' does not exist.")
        sys.exit(1)

    # Get current files in folder recursively
    files_to_index = get_files_to_index(folder)
    current_files = {str(f.relative_to(folder)) for f in files_to_index}
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
    
    for rel_path_str in sorted(current_files):
        file_path = folder / rel_path_str
        print(f"  {rel_path_str}")
        try:
            with open(file_path, "rb") as f:
                file = client.files.create(file=f, purpose="assistants")
            client.vector_stores.files.create(
                vector_store_id=config["vector_store_id"],
                file_id=file.id
            )
            file_ids.append(file.id)
            file_names.append(rel_path_str)
            file_id_map[rel_path_str] = file.id
        except Exception as e:
            print(f"  Error uploading {rel_path_str}: {e}")

    # Wait for indexing
    wait_for_indexing(config["vector_store_id"], timeout=args.timeout)

    # Update config
    config["file_ids"] = file_ids
    config["file_names"] = file_names
    config["file_id_map"] = file_id_map
    config["folder"] = str(folder)
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
    init_parser.add_argument("--timeout", type=int, default=600, help="Max seconds to wait for indexing (default: 600)")

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
    sync_parser.add_argument("--timeout", type=int, default=600, help="Max seconds to wait for indexing (default: 600)")

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
