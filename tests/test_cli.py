"""Unit tests for cli.py that don't require OPENAI_API_KEY."""

import subprocess
import sys
from pathlib import Path

import pytest

from cli import find_repo_root, is_ignored, build_ignore_specs


class TestFindRepoRoot:
    """Tests for find_repo_root function."""

    def test_finds_git_root(self, tmp_path):
        """Should find .git directory walking up from subdirectory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)

        result = find_repo_root(subdir)
        assert result == tmp_path

    def test_returns_none_when_no_git(self, tmp_path):
        """Should return None when no .git directory exists."""
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)

        result = find_repo_root(subdir)
        assert result is None


class TestIsIgnored:
    """Tests for is_ignored function with build_ignore_specs."""

    def test_ignores_dot_git(self, tmp_path):
        """Should ignore .git directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        git_file = git_dir / "config"
        git_file.touch()

        specs = build_ignore_specs(tmp_path)
        assert is_ignored(git_file, specs)

    def test_ignores_dot_env(self, tmp_path):
        """Should ignore .env file."""
        env_file = tmp_path / ".env"
        env_file.touch()

        specs = build_ignore_specs(tmp_path)
        assert is_ignored(env_file, specs)

    def test_does_not_ignore_regular_file(self, tmp_path):
        """Should not ignore regular files."""
        regular_file = tmp_path / "readme.txt"
        regular_file.touch()

        specs = build_ignore_specs(tmp_path)
        assert not is_ignored(regular_file, specs)


class TestCliHelp:
    """Tests for CLI --help without OPENAI_API_KEY."""

    def test_help_works_without_api_key(self):
        """CLI --help should work without OPENAI_API_KEY set."""
        result = subprocess.run(
            [sys.executable, "cli.py", "--help"],
            capture_output=True,
            text=True,
            env={},  # Empty env, no OPENAI_API_KEY
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "agentic-search" in result.stdout
        assert "Search documents using OpenAI vector stores" in result.stdout
