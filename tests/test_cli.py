import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli

from cli import find_repo_root, get_version, iter_document_files


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


class DummyFileCounts:
    def __init__(self, completed: int = 1, failed: int = 0, in_progress: int = 0) -> None:
        self.completed = completed
        self.failed = failed
        self.in_progress = in_progress


class DummyVectorStoreFiles:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.created: list[tuple[str, str]] = []

    def delete(self, vector_store_id: str, file_id: str) -> None:
        self.deleted.append((vector_store_id, file_id))

    def create(self, vector_store_id: str, file_id: str) -> None:
        self.created.append((vector_store_id, file_id))


class DummyVectorStores:
    def __init__(self, file_counts: DummyFileCounts | None = None) -> None:
        self.files = DummyVectorStoreFiles()
        self._file_counts = file_counts or DummyFileCounts()
        self.created: list[tuple[str, list[str]]] = []
        self.deleted: list[str] = []

    def create(self, name: str, file_ids: list[str]) -> SimpleNamespace:
        self.created.append((name, list(file_ids)))
        return SimpleNamespace(id="vs_1", file_counts=self._file_counts)

    def retrieve(self, vector_store_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=vector_store_id,
            status="completed",
            usage_bytes=1234,
            file_counts=self._file_counts,
        )

    def delete(self, vector_store_id: str) -> None:
        self.deleted.append(vector_store_id)


class DummyFiles:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.deleted: list[str] = []

    def create(self, file, purpose: str) -> SimpleNamespace:  # noqa: ANN001
        file_id = f"file_{len(self.created) + 1}"
        self.created.append(file_id)
        return SimpleNamespace(id=file_id)

    def delete(self, file_id: str) -> None:
        self.deleted.append(file_id)


class DummyAssistants:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.deleted: list[str] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.created.append(kwargs)
        return SimpleNamespace(id="asst_1")

    def delete(self, assistant_id: str) -> None:
        self.deleted.append(assistant_id)


class DummyThreadRuns:
    def __init__(self, status: str) -> None:
        self.status = status

    def create_and_poll(self, thread_id: str, assistant_id: str) -> SimpleNamespace:
        return SimpleNamespace(status=self.status, id="run_1")


class DummyThreadMessages:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def list(self, thread_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    content=[SimpleNamespace(text=SimpleNamespace(value=self.answer))]
                )
            ]
        )


class DummyThreads:
    def __init__(self, status: str, answer: str) -> None:
        self.runs = DummyThreadRuns(status)
        self.messages = DummyThreadMessages(answer)

    def create(self, messages: list[dict[str, str]]) -> SimpleNamespace:
        return SimpleNamespace(id="thread_1")


class DummyBeta:
    def __init__(self, status: str, answer: str) -> None:
        self.assistants = DummyAssistants()
        self.threads = DummyThreads(status, answer)


class DummyClient:
    def __init__(
        self,
        *,
        status: str = "completed",
        answer: str = "OK",
        file_counts: DummyFileCounts | None = None,
    ) -> None:
        self.files = DummyFiles()
        self.vector_stores = DummyVectorStores(file_counts=file_counts)
        self.beta = DummyBeta(status, answer)


def test_read_version_from_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[tool.other]",
                "name = 'ignored'",
                "[project]",
                "version = \"1.2.3\"",
            ]
        )
    )

    assert cli._read_version_from_pyproject(pyproject) == "1.2.3"
    assert cli._read_version_from_pyproject(tmp_path / "missing.toml") == "0.0.0"


def test_read_version_from_pyproject_no_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'agentic-search'\n")
    assert cli._read_version_from_pyproject(pyproject) == "0.0.0"


def test_get_version_fallback(monkeypatch) -> None:
    def raise_missing(_name: str) -> str:
        raise cli.metadata.PackageNotFoundError

    monkeypatch.setattr(cli.metadata, "version", raise_missing)
    monkeypatch.setattr(cli, "_read_version_from_pyproject", lambda _path: "9.9.9")

    assert cli.get_version() == "9.9.9"


def test_get_client_caches(monkeypatch) -> None:
    class DummyOpenAI:
        def __init__(self) -> None:
            self.marker = "ok"

    monkeypatch.setattr(cli, "OpenAI", DummyOpenAI)
    monkeypatch.setattr(cli, "_client", None)

    client_first = cli.get_client()
    client_second = cli.get_client()

    assert client_first is client_second


def test_load_ignore_lines(tmp_path: Path) -> None:
    missing = tmp_path / "missing.ignore"
    assert cli.load_ignore_lines(missing) == []

    ignore = tmp_path / ".agentic_search_ignore"
    ignore.write_text("foo\nbar\n")
    assert cli.load_ignore_lines(ignore) == ["foo", "bar"]


def test_build_ignore_specs_includes_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs"
    (repo_root / ".git").mkdir(parents=True)
    docs.mkdir(parents=True)
    (repo_root / ".gitignore").write_text("*.tmp\n")

    specs = cli.build_ignore_specs(docs)
    assert len(specs) >= 2


def test_build_ignore_specs_includes_root_ignore(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs"
    (repo_root / ".git").mkdir(parents=True)
    docs.mkdir(parents=True)
    (repo_root / ".agentic_search_ignore").write_text("secrets/\n")

    specs = cli.build_ignore_specs(docs)
    assert len(specs) >= 3


def test_is_ignored_matches_pathspec(tmp_path: Path) -> None:
    spec = cli.PathSpec.from_lines("gitwildmatch", ["*.env"])
    specs = [(spec, tmp_path)]
    assert cli.is_ignored(tmp_path / "secrets.env", specs) is True
    assert cli.is_ignored(tmp_path / "notes.txt", specs) is False


def test_is_ignored_handles_non_relative_base(tmp_path: Path) -> None:
    target = (tmp_path / "docs" / "hidden.txt").as_posix()
    spec = cli.PathSpec.from_lines("gitwildmatch", [target])
    specs = [(spec, tmp_path / "other")]
    assert cli.is_ignored(tmp_path / "docs/hidden.txt", specs) is True


def test_wait_for_indexing_completes() -> None:
    client = DummyClient(file_counts=DummyFileCounts(in_progress=0))
    cli.wait_for_indexing("vs_1", 5, client)


def test_wait_for_indexing_backoff(monkeypatch) -> None:
    counts = [DummyFileCounts(in_progress=1), DummyFileCounts(in_progress=0)]

    class SequenceVectorStores(DummyVectorStores):
        def retrieve(self, vector_store_id: str) -> SimpleNamespace:
            return SimpleNamespace(
                id=vector_store_id,
                status="in_progress",
                usage_bytes=1234,
                file_counts=counts.pop(0),
            )

    client = DummyClient()
    client.vector_stores = SequenceVectorStores()

    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    cli.wait_for_indexing("vs_1", 5, client)


def test_wait_for_indexing_times_out(monkeypatch) -> None:
    client = DummyClient(file_counts=DummyFileCounts(in_progress=1))

    times = iter([0.0, 999.0])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    with pytest.raises(SystemExit):
        cli.wait_for_indexing("vs_1", 1, client)


def test_save_and_load_config_round_trip(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))

    data = {"vector_store_id": "vs_1"}
    cli.save_config(data)
    assert cli.load_config() == data


def test_load_config_missing_prints_error(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "missing.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))

    with pytest.raises(SystemExit):
        cli.load_config()
    out = capsys.readouterr().out
    assert "Not initialized" in out


def test_cmd_list_prints_docs(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: {"file_names": ["a.txt", "b.txt"]})
    cli.cmd_list(SimpleNamespace())
    out = capsys.readouterr().out
    assert "Indexed documents:" in out
    assert "a.txt" in out


def test_cmd_list_handles_empty(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: {"file_names": []})
    cli.cmd_list(SimpleNamespace())
    assert "No documents indexed." in capsys.readouterr().out


def test_cmd_stats_prints_summary(monkeypatch, capsys) -> None:
    client = DummyClient()
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: {
            "vector_store_id": "vs_1",
            "file_names": ["a.txt"],
            "folder": "/tmp/docs",
        },
    )

    cli.cmd_stats(SimpleNamespace())
    out = capsys.readouterr().out
    assert "Vector Store:" in out
    assert "Documents:" in out


def test_cmd_init_happy_path(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("A")
    (docs / "b.txt").write_text("B")

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))

    client = DummyClient()
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(cli, "wait_for_indexing", lambda *_args: None)

    args = SimpleNamespace(folder=str(docs), index_timeout=1)
    cli.cmd_init(args)

    saved = json.loads(config_path.read_text())
    assert saved["assistant_id"] == "asst_1"
    assert saved["vector_store_id"] == "vs_1"
    assert sorted(saved["file_names"]) == ["a.txt", "b.txt"]


def test_cmd_init_missing_folder(monkeypatch) -> None:
    monkeypatch.setattr(cli, "get_client", lambda: DummyClient())

    with pytest.raises(SystemExit):
        cli.cmd_init(SimpleNamespace(folder="/missing", index_timeout=1))


def test_cmd_init_empty_folder(tmp_path: Path, monkeypatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(cli, "get_client", lambda: DummyClient())
    monkeypatch.setattr(cli, "wait_for_indexing", lambda *_args: None)

    with pytest.raises(SystemExit):
        cli.cmd_init(SimpleNamespace(folder=str(empty), index_timeout=1))


def test_cmd_init_existing_cancel(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(cli, "get_client", lambda: DummyClient())
    monkeypatch.setattr(cli, "wait_for_indexing", lambda *_args: None)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    docs = tmp_path / "docs"
    docs.mkdir()

    cli.cmd_init(SimpleNamespace(folder=str(docs), index_timeout=1))
    out = capsys.readouterr().out
    assert "Cancelled." in out


def test_cmd_ask_success(monkeypatch, capsys) -> None:
    client = DummyClient(status="completed", answer="hello")
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(
        cli, "load_config", lambda: {"assistant_id": "asst_1", "file_names": ["a"]}
    )

    cli.cmd_ask(SimpleNamespace(question="Q?"))
    out = capsys.readouterr().out
    assert "hello" in out


def test_cmd_ask_failure(monkeypatch, capsys) -> None:
    client = DummyClient(status="failed")
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(
        cli, "load_config", lambda: {"assistant_id": "asst_1", "file_names": ["a"]}
    )

    with pytest.raises(SystemExit):
        cli.cmd_ask(SimpleNamespace(question="Q?"))
    err = capsys.readouterr().err
    assert "Run failed" in err


def test_cmd_sync_no_changes(tmp_path: Path, monkeypatch, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("A")

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "vector_store_id": "vs_1",
                "file_names": ["a.txt"],
                "file_ids": ["file_1"],
            }
        )
    )

    client = DummyClient()
    monkeypatch.setattr(cli, "get_client", lambda: client)

    cli.cmd_sync(SimpleNamespace(folder=str(docs), index_timeout=1, yes=True))
    out = capsys.readouterr().out
    assert "No changes needed." in out


def test_cmd_sync_missing_folder(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "vector_store_id": "vs_1",
                "file_names": [],
                "file_ids": [],
            }
        )
    )
    monkeypatch.setattr(cli, "get_client", lambda: DummyClient())

    with pytest.raises(SystemExit):
        cli.cmd_sync(SimpleNamespace(folder=str(tmp_path / "missing"), index_timeout=1))


def test_cmd_sync_prompt_cancel(tmp_path: Path, monkeypatch, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("A")

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "vector_store_id": "vs_1",
                "file_names": [],
                "file_ids": [],
            }
        )
    )
    monkeypatch.setattr(cli, "get_client", lambda: DummyClient())
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    cli.cmd_sync(SimpleNamespace(folder=str(docs), index_timeout=1, yes=False))
    out = capsys.readouterr().out
    assert "Cancelled." in out


def test_cmd_sync_updates_config(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("A")
    (docs / "b.txt").write_text("B")

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "vector_store_id": "vs_1",
                "file_names": ["a.txt", "old.txt"],
                "file_ids": ["file_1", "file_2"],
                "folder": str(docs),
            }
        )
    )

    client = DummyClient()
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(cli, "wait_for_indexing", lambda *_args: None)

    cli.cmd_sync(SimpleNamespace(folder=str(docs), index_timeout=1, yes=True))

    saved = json.loads(config_path.read_text())
    assert sorted(saved["file_names"]) == ["a.txt", "b.txt"]
    assert client.files.deleted == ["file_1", "file_2"]
    assert set(client.vector_stores.files.deleted) == {
        ("vs_1", "file_1"),
        ("vs_1", "file_2"),
    }


def test_cmd_cleanup_handles_missing(monkeypatch, capsys) -> None:
    def raise_missing():
        raise SystemExit(1)

    monkeypatch.setattr(cli, "load_config", raise_missing)
    monkeypatch.setattr(cli, "get_client", lambda: DummyClient())

    cli.cmd_cleanup(SimpleNamespace(yes=True))
    out = capsys.readouterr().out
    assert "Nothing to clean up." in out


def test_cmd_cleanup_prompt_cancel(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "assistant_id": "asst_1",
                "vector_store_id": "vs_1",
                "file_ids": ["file_1"],
            }
        )
    )

    client = DummyClient()
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: json.loads(config_path.read_text()),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    cli.cmd_cleanup(SimpleNamespace(yes=False))
    out = capsys.readouterr().out
    assert "Cancelled." in out


def test_cmd_cleanup_deletes_resources(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "assistant_id": "asst_1",
                "vector_store_id": "vs_1",
                "file_ids": ["file_1", "file_2"],
            }
        )
    )

    client = DummyClient()
    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: json.loads(config_path.read_text()),
    )

    cli.cmd_cleanup(SimpleNamespace(yes=True))
    assert not config_path.exists()
    assert client.beta.assistants.deleted == ["asst_1"]
    assert client.vector_stores.deleted == ["vs_1"]
    assert client.files.deleted == ["file_1", "file_2"]


def test_cmd_cleanup_handles_delete_errors(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", str(config_path))
    config_path.write_text(
        json.dumps(
            {
                "assistant_id": "asst_1",
                "vector_store_id": "vs_1",
                "file_ids": ["file_1"],
            }
        )
    )

    client = DummyClient()

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    client.beta.assistants.delete = boom
    client.vector_stores.delete = boom
    client.files.delete = boom

    monkeypatch.setattr(cli, "get_client", lambda: client)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: json.loads(config_path.read_text()),
    )

    cli.cmd_cleanup(SimpleNamespace(yes=True))
    out = capsys.readouterr().out
    assert "Warning" in out


def test_main_dispatches_list(monkeypatch) -> None:
    called = {}

    def record(_args):
        called["list"] = True

    monkeypatch.setattr(cli, "cmd_list", record)
    monkeypatch.setattr(sys, "argv", ["cli.py", "list"])

    cli.main()
    assert called.get("list") is True


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
