import os
import subprocess
import sys
from pathlib import Path

from pathspec import PathSpec

from cli import find_repo_root, iter_document_files, load_ignore_lines, is_ignored


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


def test_cli_help_without_api_key() -> None:
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


def test_load_ignore_lines(tmp_path: Path) -> None:
    ignore_file = tmp_path / ".ignore"
    ignore_file.write_text("*.log\n# comment\ntemp/")
    lines = load_ignore_lines(ignore_file)
    assert lines == ["*.log", "# comment", "temp/"]


def test_load_ignore_lines_missing_file(tmp_path: Path) -> None:
    assert load_ignore_lines(tmp_path / "missing") == []


def test_is_ignored_logic() -> None:
    # Test direct is_ignored logic without file system
    spec = PathSpec.from_lines("gitwildmatch", ["*.secret"])
    base = Path("/project")
    specs = [(spec, base)]

    assert is_ignored(base / "my.secret", specs) is True
    assert is_ignored(base / "public.txt", specs) is False
    
    # Test relative path logic
    assert is_ignored(base / "subdir" / "deep.secret", specs) is True