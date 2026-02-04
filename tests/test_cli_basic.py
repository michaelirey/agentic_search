import os
import subprocess
import sys
from pathlib import Path

import cli


def test_help_works_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[1] / "cli.py"), "-h"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "agentic-search" in result.stdout


def test_iter_document_files_respects_ignore(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / ".gitignore").write_text("ignored.txt\n")

    docs = repo_root / "docs"
    docs.mkdir()
    (docs / "keep.txt").write_text("keep")
    (docs / "ignored.txt").write_text("nope")

    entries = cli.iter_document_files(docs)
    assert [name for name, _ in entries] == ["keep.txt"]


def test_find_repo_root_walks_up(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    nested = repo_root / "a" / "b"
    nested.mkdir(parents=True)

    assert cli.find_repo_root(nested) == repo_root
