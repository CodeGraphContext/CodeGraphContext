from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import pytest

inquirerpy_stub = types.ModuleType("InquirerPy")
inquirerpy_stub.prompt = lambda *args, **kwargs: {}
sys.modules.setdefault("InquirerPy", inquirerpy_stub)

neo4j_stub = types.ModuleType("neo4j")


class _DummyDriver:
    def session(self, **_kwargs):  # pragma: no cover - import stub only
        raise RuntimeError("neo4j driver stub should not be used in tests")


class _DummyGraphDatabase:
    @staticmethod
    def driver(*_args, **_kwargs):  # pragma: no cover - import stub only
        return _DummyDriver()


neo4j_stub.GraphDatabase = _DummyGraphDatabase
neo4j_stub.Driver = _DummyDriver
sys.modules.setdefault("neo4j", neo4j_stub)

from codegraphcontext.cli import setup_wizard


def _make_neo4j_creds_file(tmp_path: Path) -> Path:
    creds_file = tmp_path / "neo4j-creds.txt"
    creds_file.write_text(
        "NEO4J_URI=bolt://localhost:7687\n"
        "NEO4J_USERNAME=neo4j\n"
        "NEO4J_PASSWORD=supersecret\n",
        encoding="utf-8",
    )
    return creds_file


@pytest.mark.parametrize("entrypoint", ["setup_existing_db", "setup_hosted_db"])
def test_file_credentials_can_proceed_after_failed_validation(tmp_path, monkeypatch, entrypoint):
    creds_file = _make_neo4j_creds_file(tmp_path)
    save_mock = MagicMock()
    prompt_mock = MagicMock(
        side_effect=[
            {"cred_method": "Add credentials from file"},
            {"use_latest": True},
            {"retry": False},
        ]
    )

    monkeypatch.setattr(setup_wizard, "prompt", prompt_mock)
    monkeypatch.setattr(setup_wizard, "find_latest_neo4j_creds_file", lambda: creds_file)
    monkeypatch.setattr(setup_wizard.DatabaseManager, "validate_config", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(setup_wizard.DatabaseManager, "test_connection", lambda *args, **kwargs: (False, "Connection failed"))
    monkeypatch.setattr(setup_wizard, "_save_neo4j_credentials", save_mock)
    monkeypatch.setattr(setup_wizard, "console", MagicMock())

    getattr(setup_wizard, entrypoint)()

    save_mock.assert_called_once_with(
        {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "supersecret",
        }
    )
    assert prompt_mock.call_count == 3


@pytest.mark.parametrize("entrypoint", ["setup_existing_db", "setup_hosted_db"])
def test_file_credentials_retry_reopens_wizard(tmp_path, monkeypatch, entrypoint):
    creds_file = _make_neo4j_creds_file(tmp_path)
    save_mock = MagicMock()
    prompt_mock = MagicMock(
        side_effect=[
            {"cred_method": "Add credentials from file"},
            {"use_latest": True},
            {"retry": True},
        ]
    )

    monkeypatch.setattr(setup_wizard, "prompt", prompt_mock)
    monkeypatch.setattr(setup_wizard, "find_latest_neo4j_creds_file", lambda: creds_file)
    monkeypatch.setattr(setup_wizard.DatabaseManager, "validate_config", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(setup_wizard.DatabaseManager, "test_connection", lambda *args, **kwargs: (False, "Connection failed"))
    monkeypatch.setattr(setup_wizard, "_save_neo4j_credentials", save_mock)
    monkeypatch.setattr(setup_wizard, "console", MagicMock())

    original_entrypoint = getattr(setup_wizard, entrypoint)
    reopen_mock = MagicMock(return_value="re-entered")
    monkeypatch.setattr(setup_wizard, entrypoint, reopen_mock)

    result = original_entrypoint()

    assert result == "re-entered"
    reopen_mock.assert_called_once()
    save_mock.assert_not_called()
    assert prompt_mock.call_count == 3
