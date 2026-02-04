"""Unit tests for cli.py - tests pure/local logic without API keys."""

import tempfile
from pathlib import Path

from pathspec import PathSpec

from cli import find_repo_root, is_ignored, load_ignore_lines


def test_find_repo_root_finds_git_directory():
    """Test that find_repo_root finds a .git directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        git_dir = root / ".git"
        git_dir.mkdir()
        subdir = root / "src" / "nested"
        subdir.mkdir(parents=True)

        result = find_repo_root(subdir)
        assert result == root


def test_find_repo_root_returns_none_when_no_git():
    """Test that find_repo_root returns None when no .git exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        subdir = root / "some" / "path"
        subdir.mkdir(parents=True)

        result = find_repo_root(subdir)
        assert result is None


def test_load_ignore_lines_reads_file():
    """Test that load_ignore_lines reads lines from a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ignore_file = Path(tmpdir) / ".gitignore"
        ignore_file.write_text("*.pyc\n__pycache__/\n.env\n")

        result = load_ignore_lines(ignore_file)
        assert result == ["*.pyc", "__pycache__/", ".env"]


def test_load_ignore_lines_returns_empty_for_missing_file():
    """Test that load_ignore_lines returns empty list for missing files."""
    result = load_ignore_lines(Path("/nonexistent/path/.gitignore"))
    assert result == []


def test_is_ignored_matches_pattern():
    """Test that is_ignored correctly matches patterns."""
    base = Path("/project")
    spec = PathSpec.from_lines("gitwildmatch", ["*.pyc", "__pycache__/", ".env"])
    specs = [(spec, base)]

    assert is_ignored(Path("/project/foo.pyc"), specs) is True
    assert is_ignored(Path("/project/__pycache__/cache.bin"), specs) is True
    assert is_ignored(Path("/project/.env"), specs) is True
    assert is_ignored(Path("/project/main.py"), specs) is False
    assert is_ignored(Path("/project/src/app.py"), specs) is False
