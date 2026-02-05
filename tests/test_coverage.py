"""Tests to increase coverage of cli.py — all offline, no API keys needed."""

import json
import types
from pathlib import Path
from unittest import mock

import pytest

import cli

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path, config=None):
    """Write a minimal config file and chdir into tmp_path."""
    if config is None:
        config = {
            "assistant_id": "asst_test",
            "vector_store_id": "vs_test",
            "file_ids": ["file_1", "file_2"],
            "file_names": ["a.txt", "b.txt"],
            "file_id_map": {"a.txt": "file_1", "b.txt": "file_2"},
            "folder": str(tmp_path / "docs"),
        }
    (tmp_path / cli.CONFIG_FILE).write_text(json.dumps(config))
    return config


# ---------------------------------------------------------------------------
# _read_version_from_pyproject
# ---------------------------------------------------------------------------


class TestReadVersionFromPyproject:
    def test_reads_version(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nversion = "1.2.3"\n')
        assert cli._read_version_from_pyproject(p) == "1.2.3"

    def test_missing_file(self, tmp_path):
        p = tmp_path / "nonexistent.toml"
        assert cli._read_version_from_pyproject(p) == "0.0.0"

    def test_no_version_key(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "foo"\n')
        assert cli._read_version_from_pyproject(p) == "0.0.0"

    def test_version_in_wrong_section(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[tool.other]\nversion = "9.9.9"\n')
        assert cli._read_version_from_pyproject(p) == "0.0.0"


# ---------------------------------------------------------------------------
# get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_returns_openai_client(self):
        cli._client = None
        with mock.patch("cli.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            result = cli.get_client()
            assert result is instance
            # calling again returns cached client
            result2 = cli.get_client()
            assert result2 is instance
            MockOpenAI.assert_called_once()
        cli._client = None  # reset


# ---------------------------------------------------------------------------
# find_repo_root
# ---------------------------------------------------------------------------


class TestFindRepoRoot:
    def test_returns_none_when_no_git(self, tmp_path):
        assert cli.find_repo_root(tmp_path) is None


# ---------------------------------------------------------------------------
# load_config / save_config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_load_config_exits_on_missing(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            cli.load_config()

    def test_load_save_roundtrip(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        data = {"key": "value"}
        cli.save_config(data)
        assert cli.load_config() == data


# ---------------------------------------------------------------------------
# wait_for_indexing
# ---------------------------------------------------------------------------


class TestWaitForIndexing:
    def test_returns_immediately_when_done(self):
        fake_vs = types.SimpleNamespace(
            file_counts=types.SimpleNamespace(completed=2, failed=0, in_progress=0)
        )
        mock_client = mock.MagicMock()
        mock_client.vector_stores.retrieve.return_value = fake_vs
        cli.wait_for_indexing("vs_test", 10, mock_client)

    def test_polls_then_completes(self):
        in_progress = types.SimpleNamespace(
            file_counts=types.SimpleNamespace(completed=1, failed=0, in_progress=1)
        )
        done = types.SimpleNamespace(
            file_counts=types.SimpleNamespace(completed=2, failed=0, in_progress=0)
        )
        mock_client = mock.MagicMock()
        mock_client.vector_stores.retrieve.side_effect = [in_progress, done]
        with mock.patch("cli.time.sleep"):
            cli.wait_for_indexing("vs_test", 60, mock_client)

    def test_times_out(self):
        stuck = types.SimpleNamespace(
            file_counts=types.SimpleNamespace(completed=0, failed=0, in_progress=1)
        )
        mock_client = mock.MagicMock()
        mock_client.vector_stores.retrieve.return_value = stuck
        with (
            mock.patch("cli.time.sleep"),
            mock.patch("cli.time.monotonic", side_effect=[0, 0, 601]),
        ):
            with pytest.raises(SystemExit):
                cli.wait_for_indexing("vs_test", 600, mock_client)


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_lists_documents(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        cli.cmd_list(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "a.txt" in out
        assert "b.txt" in out

    def test_no_documents(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            config={
                "assistant_id": "asst_test",
                "vector_store_id": "vs_test",
                "file_ids": [],
                "file_names": [],
                "file_id_map": {},
                "folder": str(tmp_path),
            },
        )
        cli.cmd_list(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "No documents indexed" in out


# ---------------------------------------------------------------------------
# cmd_stats
# ---------------------------------------------------------------------------


class TestCmdStats:
    def test_prints_stats(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        fake_vs = types.SimpleNamespace(
            id="vs_test",
            status="completed",
            usage_bytes=12345,
            file_counts=types.SimpleNamespace(completed=2, failed=0, in_progress=0),
        )
        mock_client = mock.MagicMock()
        mock_client.vector_stores.retrieve.return_value = fake_vs
        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_stats(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "vs_test" in out
        assert "12,345" in out


# ---------------------------------------------------------------------------
# cmd_cleanup
# ---------------------------------------------------------------------------


class TestCmdCleanup:
    def test_cleanup_deletes_resources(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_cleanup(types.SimpleNamespace(yes=True))
        mock_client.beta.assistants.delete.assert_called_once_with("asst_test")
        mock_client.vector_stores.delete.assert_called_once_with("vs_test")
        assert not (tmp_path / cli.CONFIG_FILE).exists()

    def test_cleanup_nothing(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_cleanup(types.SimpleNamespace(yes=True))
        out = capsys.readouterr().out
        assert "Nothing to clean up" in out

    def test_cleanup_cancelled(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            with mock.patch("builtins.input", return_value="n"):
                cli.cmd_cleanup(types.SimpleNamespace(yes=False))
        out = capsys.readouterr().out
        assert "Cancelled" in out

    def test_cleanup_handles_api_errors(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        mock_client = mock.MagicMock()
        mock_client.beta.assistants.delete.side_effect = Exception("not found")
        mock_client.vector_stores.delete.side_effect = Exception("not found")
        mock_client.files.delete.side_effect = Exception("not found")
        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_cleanup(types.SimpleNamespace(yes=True))
        out = capsys.readouterr().out
        assert "Warning" in out


# ---------------------------------------------------------------------------
# cmd_ask
# ---------------------------------------------------------------------------


class TestCmdAsk:
    def test_ask_prints_answer(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        mock_client = mock.MagicMock()
        fake_text = types.SimpleNamespace(value="The answer is 42.")
        fake_content = types.SimpleNamespace(text=fake_text)
        fake_message = types.SimpleNamespace(content=[fake_content])
        mock_client.beta.threads.messages.list.return_value = types.SimpleNamespace(
            data=[fake_message]
        )
        fake_run = types.SimpleNamespace(status="completed")
        mock_client.beta.threads.runs.create_and_poll.return_value = fake_run
        mock_client.beta.threads.create.return_value = types.SimpleNamespace(
            id="thread_test"
        )
        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_ask(types.SimpleNamespace(question="What is the answer?"))
        out = capsys.readouterr().out
        assert "42" in out

    def test_ask_failed_run(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        mock_client = mock.MagicMock()
        fake_run = types.SimpleNamespace(status="failed")
        mock_client.beta.threads.runs.create_and_poll.return_value = fake_run
        mock_client.beta.threads.create.return_value = types.SimpleNamespace(
            id="thread_test"
        )
        with mock.patch("cli.get_client", return_value=mock_client):
            with pytest.raises(SystemExit):
                cli.cmd_ask(types.SimpleNamespace(question="Will this fail?"))


# ---------------------------------------------------------------------------
# cmd_init
# ---------------------------------------------------------------------------


class TestCmdInit:
    def test_init_creates_resources(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "readme.txt").write_text("hello world")

        mock_client = mock.MagicMock()
        mock_client.files.create.return_value = types.SimpleNamespace(id="file_new")
        mock_client.vector_stores.create.return_value = types.SimpleNamespace(
            id="vs_new"
        )
        mock_client.beta.assistants.create.return_value = types.SimpleNamespace(
            id="asst_new"
        )
        # indexing completes immediately
        fake_vs = types.SimpleNamespace(
            file_counts=types.SimpleNamespace(completed=1, failed=0, in_progress=0)
        )
        mock_client.vector_stores.retrieve.return_value = fake_vs

        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_init(types.SimpleNamespace(folder=str(docs), index_timeout=60))

        config = json.loads((tmp_path / cli.CONFIG_FILE).read_text())
        assert config["assistant_id"] == "asst_new"
        assert config["vector_store_id"] == "vs_new"
        assert "readme.txt" in config["file_names"]

    def test_init_no_files(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        docs = tmp_path / "empty_docs"
        docs.mkdir()
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            with pytest.raises(SystemExit):
                cli.cmd_init(types.SimpleNamespace(folder=str(docs), index_timeout=60))

    def test_init_folder_not_found(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            with pytest.raises(SystemExit):
                cli.cmd_init(
                    types.SimpleNamespace(folder="nonexistent", index_timeout=60)
                )

    def test_init_reinitialize_cancelled(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "file.txt").write_text("content")
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            with mock.patch("builtins.input", return_value="n"):
                cli.cmd_init(types.SimpleNamespace(folder=str(docs), index_timeout=60))
        out = capsys.readouterr().out
        assert "Cancelled" in out


# ---------------------------------------------------------------------------
# cmd_sync
# ---------------------------------------------------------------------------


class TestCmdSync:
    def test_sync_no_changes(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.txt").write_text("content a")
        (docs / "b.txt").write_text("content b")
        _write_config(tmp_path)

        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_sync(
                types.SimpleNamespace(folder=str(docs), index_timeout=60, yes=False)
            )
        out = capsys.readouterr().out
        assert "No changes needed" in out

    def test_sync_with_changes(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.txt").write_text("content a")
        (docs / "c.txt").write_text("new file")
        _write_config(tmp_path)

        mock_client = mock.MagicMock()
        mock_client.files.create.return_value = types.SimpleNamespace(id="file_c")
        fake_vs = types.SimpleNamespace(
            file_counts=types.SimpleNamespace(completed=2, failed=0, in_progress=0)
        )
        mock_client.vector_stores.retrieve.return_value = fake_vs

        with mock.patch("cli.get_client", return_value=mock_client):
            cli.cmd_sync(
                types.SimpleNamespace(folder=str(docs), index_timeout=60, yes=True)
            )
        out = capsys.readouterr().out
        assert "c.txt" in out
        assert "b.txt" in out  # removed

        config = json.loads((tmp_path / cli.CONFIG_FILE).read_text())
        assert "c.txt" in config["file_names"]

    def test_sync_cancelled(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "new_file.txt").write_text("new")
        _write_config(tmp_path)

        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            with mock.patch("builtins.input", return_value="n"):
                cli.cmd_sync(
                    types.SimpleNamespace(folder=str(docs), index_timeout=60, yes=False)
                )
        out = capsys.readouterr().out
        assert "Cancelled" in out

    def test_sync_folder_not_found(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        mock_client = mock.MagicMock()
        with mock.patch("cli.get_client", return_value=mock_client):
            with pytest.raises(SystemExit):
                cli.cmd_sync(
                    types.SimpleNamespace(
                        folder="nonexistent", index_timeout=60, yes=False
                    )
                )


# ---------------------------------------------------------------------------
# main (argument parsing)
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_no_args(self):
        with mock.patch("sys.argv", ["cli.py"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
            assert exc_info.value.code == 2

    def test_main_dispatches_list(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with mock.patch("sys.argv", ["cli.py", "list"]):
            cli.main()
        out = capsys.readouterr().out
        assert "a.txt" in out


# ---------------------------------------------------------------------------
# build_ignore_specs edge cases
# ---------------------------------------------------------------------------


class TestBuildIgnoreSpecs:
    def test_no_repo_root(self, tmp_path):
        folder = tmp_path / "standalone"
        folder.mkdir()
        specs = cli.build_ignore_specs(folder)
        # should have default patterns only (no gitignore, no repo-level ignore)
        assert len(specs) == 1

    def test_with_repo_and_folder_ignore(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        docs = repo / "docs"
        docs.mkdir()
        (repo / ".gitignore").write_text("*.log\n")
        (repo / ".agentic_search_ignore").write_text("*.tmp\n")
        (docs / ".agentic_search_ignore").write_text("*.bak\n")
        specs = cli.build_ignore_specs(docs)
        # default for folder, default for repo, gitignore, root ignore, folder ignore
        assert len(specs) == 5


# ---------------------------------------------------------------------------
# is_ignored edge cases
# ---------------------------------------------------------------------------


class TestIsIgnored:
    def test_path_not_relative_to_base(self, tmp_path):
        spec = cli.PathSpec.from_lines("gitwildmatch", ["*.log"])
        other = Path("/some/other/path/test.log")
        # Should not crash when path is not relative to base
        result = cli.is_ignored(other, [(spec, tmp_path)])
        assert isinstance(result, bool)
