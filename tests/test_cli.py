import os
import subprocess
import sys
from pathlib import Path

from cli import (
    build_file_id_to_name_map,
    extract_citations,
    find_repo_root,
    format_sources,
    get_version,
    iter_document_files,
)


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


# Mock classes to simulate OpenAI API response structure
class MockFileCitation:
    def __init__(self, file_id: str, quote: str = ""):
        self.file_id = file_id
        self.quote = quote


class MockAnnotation:
    def __init__(self, file_id: str, start_index: int, end_index: int, quote: str = ""):
        self.file_citation = MockFileCitation(file_id, quote)
        self.start_index = start_index
        self.end_index = end_index


class MockTextBlock:
    def __init__(self, value: str, annotations: list | None = None):
        self.value = value
        self.annotations = annotations


def test_build_file_id_to_name_map() -> None:
    config = {
        "file_id_map": {
            "docs/readme.md": "file-abc123",
            "src/main.py": "file-def456",
        }
    }
    result = build_file_id_to_name_map(config)
    assert result == {
        "file-abc123": "docs/readme.md",
        "file-def456": "src/main.py",
    }


def test_build_file_id_to_name_map_empty() -> None:
    config = {}
    result = build_file_id_to_name_map(config)
    assert result == {}


def test_extract_citations_no_annotations() -> None:
    text_block = MockTextBlock("This is a plain answer without citations.")
    file_id_to_name = {"file-abc": "doc.md"}

    text, citations = extract_citations(text_block, file_id_to_name)

    assert text == "This is a plain answer without citations."
    assert citations == []


def test_extract_citations_with_single_citation() -> None:
    # Simulates: "Answer text【0†source】more text"
    # The marker 【0†source】 spans character indices 11-21
    text_block = MockTextBlock(
        "Answer text【0†source】more text",
        annotations=[
            MockAnnotation("file-abc", 11, 21, "This is the quote"),
        ],
    )
    file_id_to_name = {"file-abc": "architecture.md"}

    text, citations = extract_citations(text_block, file_id_to_name)

    assert text == "Answer text[1]more text"
    assert len(citations) == 1
    assert citations[0]["number"] == 1
    assert citations[0]["file_name"] == "architecture.md"
    assert citations[0]["quote"] == "This is the quote"


def test_extract_citations_with_multiple_citations() -> None:
    # Simulates: "First【0†source】and second【1†source】"
    # First marker 【0†source】 spans 5-15, second 【1†source】 spans 25-35
    text_block = MockTextBlock(
        "First【0†source】and second【1†source】",
        annotations=[
            MockAnnotation("file-abc", 5, 15, "Quote one"),
            MockAnnotation("file-def", 25, 35, "Quote two"),
        ],
    )
    file_id_to_name = {
        "file-abc": "doc1.md",
        "file-def": "doc2.md",
    }

    text, citations = extract_citations(text_block, file_id_to_name)

    assert text == "First[1]and second[2]"
    assert len(citations) == 2
    assert citations[0]["number"] == 1
    assert citations[0]["file_name"] == "doc1.md"
    assert citations[1]["number"] == 2
    assert citations[1]["file_name"] == "doc2.md"


def test_extract_citations_same_file_multiple_times() -> None:
    # Same file cited twice should reuse the same citation number
    # First marker 【0†source】 spans 5-15, second 【1†source】 spans 25-35
    text_block = MockTextBlock(
        "First【0†source】and second【1†source】",
        annotations=[
            MockAnnotation("file-abc", 5, 15, "Quote one"),
            MockAnnotation("file-abc", 25, 35, "Quote two"),
        ],
    )
    file_id_to_name = {"file-abc": "doc.md"}

    text, citations = extract_citations(text_block, file_id_to_name)

    assert text == "First[1]and second[1]"
    # Only one citation entry since it's the same file
    assert len(citations) == 1
    assert citations[0]["number"] == 1


def test_extract_citations_unknown_file_id() -> None:
    text_block = MockTextBlock(
        "Text【0†source】",
        annotations=[
            MockAnnotation("file-unknown", 4, 15, "Some quote"),
        ],
    )
    file_id_to_name = {}  # Empty map

    text, citations = extract_citations(text_block, file_id_to_name)

    assert text == "Text[1]"
    assert len(citations) == 1
    assert citations[0]["file_name"] == "Unknown"


def test_extract_citations_empty_quote() -> None:
    text_block = MockTextBlock(
        "Text【0†source】",
        annotations=[
            MockAnnotation("file-abc", 4, 15, ""),
        ],
    )
    file_id_to_name = {"file-abc": "doc.md"}

    text, citations = extract_citations(text_block, file_id_to_name)

    assert len(citations) == 1
    assert citations[0]["quote"] == ""


def test_format_sources_empty() -> None:
    result = format_sources([])
    assert result == ""


def test_format_sources_compact() -> None:
    citations = [
        {"number": 1, "file_name": "doc1.md", "quote": "Some quote"},
        {"number": 2, "file_name": "doc2.py", "quote": "Another quote"},
    ]

    result = format_sources(citations, verbose=False)

    assert "Sources:" in result
    assert "[1] doc1.md" in result
    assert "[2] doc2.py" in result
    # Quotes should not appear in compact mode
    assert "Some quote" not in result
    assert "Another quote" not in result


def test_format_sources_verbose() -> None:
    citations = [
        {"number": 1, "file_name": "doc1.md", "quote": "Some quote"},
        {"number": 2, "file_name": "doc2.py", "quote": "Another quote"},
    ]

    result = format_sources(citations, verbose=True)

    assert "Sources:" in result
    assert "[1] doc1.md" in result
    assert "[2] doc2.py" in result
    # Quotes should appear in verbose mode
    assert '"Some quote"' in result
    assert '"Another quote"' in result


def test_format_sources_verbose_empty_quote() -> None:
    citations = [
        {"number": 1, "file_name": "doc.md", "quote": ""},
    ]

    result = format_sources(citations, verbose=True)

    assert "[1] doc.md" in result
    # Should not have empty quote line
    assert '""' not in result
