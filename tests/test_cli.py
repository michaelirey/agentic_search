import json
import os
import subprocess
import sys
import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
from cli import (
    find_repo_root,
    get_version,
    iter_document_files,
    cmd_init,
    cmd_ask,
    cmd_list,
    cmd_stats,
    cmd_sync,
    cmd_cleanup,
    main,
    CONFIG_FILE,
)

# --- Existing Tests ---

def test_find_repo_root_walks_up(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    nested = repo_root / "docs" / "sub"
    nested.mkdir(parents=True)

    assert find_repo_root(nested) == repo_root


def test_iter_document_files_respects_ignores(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs"
    (repo_root / ".git").mkdir(parents=True)
    docs.mkdir(parents=True)

    (repo_root / ".gitignore").write_text("docs/ignored.txt\n")
    (docs / ".agentic_search_ignore").write_text("subdir/\n")

    (docs / "keep.txt").write_text("ok")
    (docs / "ignored.txt").write_text("no")
    (docs / ".env").write_text("SECRET=1")
    (docs / ".agentic_search_config.json").write_text("{}")

    subdir = docs / "subdir"
    subdir.mkdir()
    (subdir / "hidden.md").write_text("hidden")

    rel_paths = {rel for rel, _ in iter_document_files(docs)}
    assert rel_paths == {"keep.txt"}


def test_get_version() -> None:
    v = get_version()
    assert isinstance(v, str)
    assert len(v) > 0


def test_cli_help_without_api_key() -> None:
    """Ensure CLI help works without API key (imports don't crash)."""
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)

    result = subprocess.run(
        [sys.executable, "cli.py", "--help"],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "agentic-search" in result.stdout


# --- New Tests for CLI Commands ---

@pytest.fixture(autouse=True)
def mock_openai_env():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}):
        yield
    # Teardown: Reset singleton client to avoid leakage across tests
    import cli
    cli._client = None

@pytest.fixture
def mock_client():
    with patch("cli.get_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_config_path(tmp_path):
    """Isolate CONFIG_FILE to a temp path to prevent deleting real config."""
    config_path = tmp_path / ".agentic_search_config.json"
    with patch("cli.CONFIG_FILE", str(config_path)):
        yield config_path

@pytest.fixture
def mock_config(mock_config_path):
    # Mock load_config and save_config via file operations or directly patching
    config = {
        "assistant_id": "asst_123",
        "vector_store_id": "vs_123",
        "file_ids": ["file_123"],
        "file_names": ["doc.txt"],
        "file_id_map": {"doc.txt": "file_123"},
        "folder": "/tmp/docs",
    }
    with patch("cli.load_config", return_value=config):
        yield config

@pytest.fixture
def mock_save_config():
    with patch("cli.save_config") as mock:
        yield mock

def test_cmd_init(tmp_path, mock_client, mock_save_config, mock_config_path):
    # Setup
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.txt").write_text("content")
    
    args = argparse.Namespace(folder=str(docs_dir), index_timeout=10, command="init")
    
    # Mock responses
    mock_file = MagicMock()
    mock_file.id = "file_1"
    mock_client.files.create.return_value = mock_file
    
    mock_vs = MagicMock()
    mock_vs.id = "vs_1"
    mock_vs.file_counts.in_progress = 0
    mock_vs.file_counts.completed = 1
    mock_vs.file_counts.failed = 0
    mock_client.vector_stores.create.return_value = mock_vs
    mock_client.vector_stores.retrieve.return_value = mock_vs
    
    mock_asst = MagicMock()
    mock_asst.id = "asst_1"
    mock_client.beta.assistants.create.return_value = mock_asst

    # Execute
    with patch("builtins.input", return_value="y"): # In case it asks for confirmation
        cmd_init(args)

    # Verify
    mock_client.files.create.assert_called_once()
    mock_client.vector_stores.create.assert_called_once()
    mock_client.beta.assistants.create.assert_called_once()
    mock_save_config.assert_called_once()
    saved_conf = mock_save_config.call_args[0][0]
    assert saved_conf["assistant_id"] == "asst_1"
    assert saved_conf["vector_store_id"] == "vs_1"
    assert "test.txt" in saved_conf["file_names"]

def test_cmd_init_errors(mock_client, tmp_path, mock_config_path):
    # Folder not exists
    args = argparse.Namespace(folder="nonexistent", index_timeout=10, command="init")
    with pytest.raises(SystemExit):
        cmd_init(args)

    # No files found
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    args.folder = str(empty_dir)
    with pytest.raises(SystemExit):
         cmd_init(args)

def test_cmd_init_already_initialized_no(mock_client, tmp_path, mock_config_path):
    # Already initialized, say no
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    args = argparse.Namespace(folder=str(docs_dir), index_timeout=10, command="init")
    
    # Create the config file to simulate existing initialization
    mock_config_path.write_text("{}")

    with patch("builtins.input", return_value="n"):
         cmd_init(args)
         # Should return without doing anything
         mock_client.files.create.assert_not_called()

def test_cmd_ask(mock_client, mock_config, capsys):
    args = argparse.Namespace(question="Hello?", command="ask")
    
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run
    
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=MagicMock(value="World!"))]
    mock_client.beta.threads.messages.list.return_value = MagicMock(data=[mock_msg])

    cmd_ask(args)
    
    captured = capsys.readouterr()
    assert "World!" in captured.out
    mock_client.beta.threads.create.assert_called_once()

def test_cmd_ask_failure(mock_client, mock_config):
    args = argparse.Namespace(question="Hello?", command="ask")
    
    mock_run = MagicMock()
    mock_run.status = "failed"
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run
    
    with pytest.raises(SystemExit):
        cmd_ask(args)

def test_cmd_list(mock_config, capsys):
    args = argparse.Namespace(command="list")
    cmd_list(args)
    captured = capsys.readouterr()
    assert "doc.txt" in captured.out

def test_cmd_list_empty(capsys):
    with patch("cli.load_config", return_value={}):
        args = argparse.Namespace(command="list")
        cmd_list(args)
        captured = capsys.readouterr()
        assert "No documents indexed" in captured.out

def test_cmd_stats(mock_client, mock_config, capsys):
    args = argparse.Namespace(command="stats")
    
    mock_vs = MagicMock()
    mock_vs.id = "vs_123"
    mock_vs.status = "completed"
    mock_vs.usage_bytes = 1024
    mock_vs.file_counts.completed = 1
    mock_vs.file_counts.failed = 0
    mock_vs.file_counts.in_progress = 0
    
    mock_client.vector_stores.retrieve.return_value = mock_vs
    
    cmd_stats(args)
    
    captured = capsys.readouterr()
    assert "vs_123" in captured.out
    assert "1,024 bytes" in captured.out

def test_cmd_cleanup(mock_client, mock_config, mock_config_path):
    args = argparse.Namespace(yes=True, command="cleanup")
    
    # Create config file so os.remove has something to remove
    mock_config_path.write_text("{}")

    cmd_cleanup(args)
    
    mock_client.beta.assistants.delete.assert_called_with("asst_123")
    mock_client.vector_stores.delete.assert_called_with("vs_123")
    mock_client.files.delete.assert_called_with("file_123")
    assert not mock_config_path.exists()

def test_cmd_cleanup_not_initialized(mock_client):
     # mock_client is unused by code but prevents leak if code called get_client
     with patch("cli.load_config", side_effect=SystemExit), \
          patch("builtins.print") as mock_print:
         cmd_cleanup(argparse.Namespace(yes=True, command="cleanup"))
         mock_print.assert_called_with("Nothing to clean up.")

def test_cmd_cleanup_no(mock_client, mock_config):
    args = argparse.Namespace(yes=False, command="cleanup")
    with patch("builtins.input", return_value="n"):
        cmd_cleanup(args)
        mock_client.beta.assistants.delete.assert_not_called()

def test_cmd_sync_no_changes(mock_client, mock_config, tmp_path, capsys):
    # Setup folder to match config
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc.txt").write_text("content")
    
    # Update mock config to match path
    mock_config["folder"] = str(docs_dir)

    args = argparse.Namespace(folder=str(docs_dir), yes=True, command="sync", index_timeout=10)
    
    cmd_sync(args)
    
    captured = capsys.readouterr()
    assert "No changes needed" in captured.out

def test_cmd_sync_folder_not_exists():
    args = argparse.Namespace(folder="nonexistent", command="sync")
    with pytest.raises(SystemExit):
        cmd_sync(args)

def test_cmd_sync_with_changes(mock_client, mock_config, mock_save_config, tmp_path):
    # Setup folder with NEW file
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc.txt").write_text("content")
    (docs_dir / "new.txt").write_text("new content")
    
    # Update mock config to match path
    mock_config["folder"] = str(docs_dir)

    args = argparse.Namespace(folder=str(docs_dir), yes=True, command="sync", index_timeout=10)
    
    # Mock responses
    mock_file = MagicMock()
    mock_file.id = "file_new"
    mock_client.files.create.return_value = mock_file
    
    mock_vs = MagicMock()
    mock_vs.file_counts.in_progress = 0
    mock_client.vector_stores.retrieve.return_value = mock_vs
    
    cmd_sync(args)
    
    # Check deletion of old file
    mock_client.vector_stores.files.delete.assert_called()
    
    # Check upload of both files (doc.txt and new.txt)
    assert mock_client.files.create.call_count == 2
    
    mock_save_config.assert_called_once()
    saved_conf = mock_save_config.call_args[0][0]
    assert "new.txt" in saved_conf["file_names"]

def test_cmd_sync_no(mock_client, mock_config, tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    # No file doc.txt so it will be removed
    
    args = argparse.Namespace(folder=str(docs_dir), yes=False, command="sync")
    with patch("builtins.input", return_value="n"):
        cmd_sync(args)
        mock_client.vector_stores.files.delete.assert_not_called()

def test_main_dispatch():
    with patch("sys.argv", ["cli.py", "stats"]), \
         patch("cli.cmd_stats") as mock_stats:
        main()
        mock_stats.assert_called_once()

def test_load_config_error():
    with patch("builtins.open", side_effect=FileNotFoundError), \
         pytest.raises(SystemExit):
        from cli import load_config
        load_config()