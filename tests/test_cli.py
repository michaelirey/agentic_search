import os
import subprocess
import sys
from pathlib import Path

from cli import _format_answer_with_sources, find_repo_root, get_version, iter_document_files


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


def test_cli_version_without_api_key() -> None:
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)

    expected_version = get_version()
    assert expected_version

    result = subprocess.run(
        [sys.executable, "cli.py", "--version"],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout.strip()
    assert output.startswith("agentic-search ")
    assert output.split(" ", 1)[1] == expected_version


def test_format_answer_with_sources_replaces_markers() -> None:
    text = "Answer with cite [source]."
    annotations = [
        {
            "text": "[source]",
            "type": "file_citation",
            "file_id": "file_abc",
            "quote": "quoted text",
        }
    ]
    formatted, sources = _format_answer_with_sources(
        text,
        annotations,
        {"file_abc": "doc.md"},
        with_sources=False,
    )

    assert formatted == "Answer with cite [1]."
    assert sources == ["Sources:", "[1] doc.md"]


def test_format_answer_with_sources_includes_quotes() -> None:
    text = "Answer with cite [source]."
    annotations = [
        {
            "text": "[source]",
            "type": "file_citation",
            "file_id": "file_abc",
            "quote": "quoted text",
        }
    ]
    formatted, sources = _format_answer_with_sources(
        text,
        annotations,
        {"file_abc": "doc.md"},
        with_sources=True,
    )

    assert formatted == "Answer with cite [1]."
    assert sources == ["Sources:", "[1] doc.md", '    "quoted text"']


def test_format_answer_with_sources_handles_unknown_and_empty_quote() -> None:
    text = "Answer with cite [source]."
    annotations = [
        {
            "text": "[source]",
            "type": "file_citation",
            "file_id": "file_missing",
            "quote": "",
        }
    ]
    formatted, sources = _format_answer_with_sources(
        text,
        annotations,
        {},
        with_sources=True,
    )

    assert formatted == "Answer with cite [1]."
    assert sources == ["Sources:", "[1] Unknown"]


def test_format_answer_with_sources_uses_start_end_indices() -> None:
    text = "Answer with citeX."
    annotations = [
        {
            "type": "file_citation",
            "file_id": "file_abc",
            "quote": "quoted text",
            "start_index": 16,
            "end_index": 17,
        }
    ]
    formatted, sources = _format_answer_with_sources(
        text,
        annotations,
        {"file_abc": "doc.md"},
        with_sources=False,
    )

    assert formatted == "Answer with cite[1]."
    assert sources == ["Sources:", "[1] doc.md"]
