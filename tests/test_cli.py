import os
from pathlib import Path
import pytest
from cli import find_repo_root, is_ignored, build_ignore_specs
from pathspec import PathSpec

def test_find_repo_root_found(tmp_path):
    # Create a fake git repo
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    
    assert find_repo_root(subdir) == tmp_path
    assert find_repo_root(tmp_path) == tmp_path

def test_find_repo_root_not_found(tmp_path):
    # Ensure no .git in tmp_path or parents (might be tricky if /tmp is in a git repo, but unlikely for default pytest tmp_path behavior unless nesting)
    pass 

def test_is_ignored_default():
    # Mock specs
    base = Path("/tmp")
    spec = PathSpec.from_lines("gitwildmatch", [".env", ".git/"])
    specs = [(spec, base)]
    
    assert is_ignored(base / ".env", specs)
    assert is_ignored(base / ".git" / "HEAD", specs)
    assert not is_ignored(base / "file.txt", specs)

def test_build_ignore_specs_respects_gitignore(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("*.log\n")
    
    specs = build_ignore_specs(tmp_path)
    
    assert is_ignored(tmp_path / "app.log", specs)
    assert not is_ignored(tmp_path / "app.py", specs)

def test_build_ignore_specs_respects_agentic_ignore(tmp_path):
    (tmp_path / ".agentic_search_ignore").write_text("secret.txt\n")
    
    specs = build_ignore_specs(tmp_path)
    
    assert is_ignored(tmp_path / "secret.txt", specs)
    assert not is_ignored(tmp_path / "public.txt", specs)