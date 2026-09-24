"""#1597: probe_embedding_backend distinguishes 'working' from 'never ran'."""
import importlib.util

import pytest

from codegraphcontext.tools.indexing import embeddings as emb


def test_openai_spec_without_key_fails(monkeypatch):
    monkeypatch.setenv("CGC_EMBEDDING_MODEL", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if importlib.util.find_spec("openai") is None:
        ok, detail = emb.probe_embedding_backend()
        assert not ok and "openai" in detail
    else:
        ok, detail = emb.probe_embedding_backend()
        assert not ok and "OPENAI_API_KEY" in detail


def test_local_spec_reports_missing_backends(monkeypatch):
    monkeypatch.setenv("CGC_EMBEDDING_MODEL", "local")
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name, *a, **k):
        if name in ("sentence_transformers", "fastembed"):
            return None
        return real_find_spec(name, *a, **k)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    ok, detail = emb.probe_embedding_backend()
    assert not ok
    assert "sentence-transformers" in detail and "fastembed" in detail


def test_local_spec_accepts_fastembed(monkeypatch):
    monkeypatch.setenv("CGC_EMBEDDING_MODEL", "local")
    real_find_spec = importlib.util.find_spec

    class _FakeSpec:  # truthy stand-in
        pass

    def fake_find_spec(name, *a, **k):
        if name == "sentence_transformers":
            return None
        if name == "fastembed":
            return _FakeSpec()
        return real_find_spec(name, *a, **k)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    ok, detail = emb.probe_embedding_backend()
    assert ok and detail == "fastembed"


def test_explicit_model_spec_overrides_env(monkeypatch):
    monkeypatch.setenv("CGC_EMBEDDING_MODEL", "local")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ok, _ = emb.probe_embedding_backend("openai")
    assert not ok
