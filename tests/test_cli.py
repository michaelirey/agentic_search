import shutil
import tempfile
from pathlib import Path
import pytest
from pathspec import PathSpec

from cli import find_repo_root, is_ignored, build_ignore_specs

@pytest.fixture
def temp_repo():
    """Create a temporary directory structure resembling a git repo."""
    temp_dir = Path(tempfile.mkdtemp())
    (temp_dir / ".git").mkdir()
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").touch()
    yield temp_dir
    shutil.rmtree(temp_dir)

def test_find_repo_root(temp_repo):
    """Test finding the repo root."""
    assert find_repo_root(temp_repo) == temp_repo
    assert find_repo_root(temp_repo / "src") == temp_repo

def test_is_ignored():
    """Test ignoring files based on patterns."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        (temp_dir / ".agentic_search_ignore").write_text("*.log\n")
        specs = build_ignore_specs(temp_dir)
        
        ignored_file = temp_dir / "test.log"
        included_file = temp_dir / "test.py"
        
        assert is_ignored(ignored_file, specs) is True
        assert is_ignored(included_file, specs) is False
    finally:
        shutil.rmtree(temp_dir)
