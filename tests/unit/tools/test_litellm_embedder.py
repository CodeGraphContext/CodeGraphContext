"""CGC_EMBEDDING_MODEL=litellm/<model>: embeddings through the LiteLLM SDK."""
import importlib.util
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from codegraphcontext.cli.config_manager import validate_config_value
from codegraphcontext.tools.indexing import embeddings as emb


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    monkeypatch.delenv("LITELLM_API_BASE", raising=False)
    monkeypatch.setenv("LITELLM_MODE", "PRODUCTION")


@pytest.fixture
def fake_litellm(monkeypatch):
    module = types.ModuleType("litellm")
    module.embedding = MagicMock(
        side_effect=lambda model, input, **_: SimpleNamespace(
            data=[{"index": i, "embedding": [float(i), 0.5, 0.25]} for i in range(len(input))]
        )
    )
    module.get_model_info = MagicMock(side_effect=Exception("model not mapped"))
    monkeypatch.setitem(sys.modules, "litellm", module)
    return module


def test_prefix_selects_litellm_embedder_without_calling_the_provider(fake_litellm):
    embedder = emb._get_embedder("litellm/cohere/embed-english-v3.0")

    assert isinstance(embedder, emb._LiteLLMEmbedder)
    assert embedder.model == "cohere/embed-english-v3.0"
    fake_litellm.embedding.assert_not_called()
    fake_litellm.get_model_info.assert_not_called()


def test_env_var_selects_litellm_embedder(monkeypatch, fake_litellm):
    monkeypatch.setenv("CGC_EMBEDDING_MODEL", "litellm/bedrock/amazon.titan-embed-text-v2:0")

    assert emb._get_embedder().model == "bedrock/amazon.titan-embed-text-v2:0"


def test_embed_batch_forwards_model_and_api_base(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_API_BASE", "http://localhost:11434/")
    embedder = emb._get_embedder("litellm/ollama/nomic-embed-text")

    vectors = embedder.embed_batch(["def foo", "def bar"])

    assert vectors == [[0.0, 0.5, 0.25], [1.0, 0.5, 0.25]]
    fake_litellm.embedding.assert_called_once_with(
        model="ollama/nomic-embed-text",
        input=["def foo", "def bar"],
        drop_params=True,
        api_base="http://localhost:11434",
    )


def test_embed_batch_leaves_credentials_to_the_provider_env(fake_litellm):
    emb._get_embedder("litellm/voyage/voyage-code-3").embed_batch(["x"])

    kwargs = fake_litellm.embedding.call_args.kwargs
    assert "api_base" not in kwargs and "api_key" not in kwargs


def test_embed_batch_restores_input_order_for_object_items(fake_litellm):
    # Some providers return items out of order and as objects rather than dicts.
    fake_litellm.embedding.side_effect = None
    fake_litellm.embedding.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=2, embedding=[2.0]),
            SimpleNamespace(index=0, embedding=[0.0]),
            SimpleNamespace(index=1, embedding=[1.0]),
        ]
    )

    vectors = emb._get_embedder("litellm/gemini/text-embedding-004").embed_batch(["a", "b", "c"])

    assert vectors == [[0.0], [1.0], [2.0]]


def test_embed_batch_rejects_a_short_response(fake_litellm):
    fake_litellm.embedding.side_effect = None
    fake_litellm.embedding.return_value = SimpleNamespace(data=[{"index": 0, "embedding": [0.1]}])

    with pytest.raises(RuntimeError, match="returned 1 embeddings for 2 inputs"):
        emb._get_embedder("litellm/cohere/embed-english-v3.0").embed_batch(["a", "b"])


def test_dim_comes_from_litellm_model_map(fake_litellm):
    fake_litellm.get_model_info.side_effect = None
    fake_litellm.get_model_info.return_value = {"output_vector_size": 1024}
    embedder = emb._get_embedder("litellm/bedrock/amazon.titan-embed-text-v2:0")

    assert embedder.dim == 1024
    fake_litellm.get_model_info.assert_called_once_with("bedrock/amazon.titan-embed-text-v2:0")
    fake_litellm.embedding.assert_not_called()


def test_dim_is_probed_once_for_unmapped_models(fake_litellm):
    embedder = emb._get_embedder("litellm/hosted_vllm/my-embedder")

    assert embedder.dim == 3
    assert embedder.dim == 3
    fake_litellm.embedding.assert_called_once()
    assert fake_litellm.suppress_debug_info is True


def test_pipeline_sizes_the_vector_index_from_the_litellm_model(fake_litellm, monkeypatch):
    fake_litellm.get_model_info.side_effect = None
    fake_litellm.get_model_info.return_value = {"output_vector_size": 1024}
    pipeline = emb.EmbeddingPipeline(MagicMock())
    sized = MagicMock()
    monkeypatch.setattr(pipeline, "_ensure_vector_index", sized)
    monkeypatch.setattr(pipeline, "_fetch_unembedded", lambda repo_path: [])

    pipeline.run("/repo", model_spec="litellm/bedrock/amazon.titan-embed-text-v2:0")

    sized.assert_called_once_with(1024)


def test_missing_litellm_package_names_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", None)

    with pytest.raises(ImportError, match=r"codegraphcontext\[litellm\]"):
        emb._get_embedder("litellm/cohere/embed-english-v3.0")


def test_prefix_without_a_model_is_rejected(fake_litellm):
    with pytest.raises(ValueError, match="needs a model"):
        emb._get_embedder("litellm/")


class TestProbe:
    def _with_litellm(self, monkeypatch, installed):
        real_find_spec = importlib.util.find_spec

        def fake_find_spec(name, *a, **k):
            if name == "litellm":
                return object() if installed else None
            return real_find_spec(name, *a, **k)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    def test_ready_when_litellm_is_installed(self, monkeypatch):
        self._with_litellm(monkeypatch, installed=True)

        assert emb.probe_embedding_backend("litellm/cohere/embed-english-v3.0") == (True, "litellm")

    def test_reports_missing_package(self, monkeypatch):
        self._with_litellm(monkeypatch, installed=False)

        ok, detail = emb.probe_embedding_backend("litellm/cohere/embed-english-v3.0")
        assert not ok
        assert "'litellm' package is not installed" in detail

    def test_reports_missing_model(self, monkeypatch):
        self._with_litellm(monkeypatch, installed=True)

        ok, detail = emb.probe_embedding_backend("litellm/")
        assert not ok and "names no model" in detail


class TestConfigValidation:
    def test_litellm_embedding_model_is_accepted(self):
        assert validate_config_value("CGC_EMBEDDING_MODEL", "litellm/bedrock/amazon.titan-embed-text-v2:0") == (
            True,
            None,
        )

    def test_litellm_prefix_without_model_is_rejected(self):
        ok, message = validate_config_value("CGC_EMBEDDING_MODEL", "litellm/")
        assert not ok and "needs a model" in message

    def test_prefix_is_case_sensitive_like_the_runtime_check(self):
        ok, _ = validate_config_value("CGC_EMBEDDING_MODEL", "LiteLLM/cohere/embed-english-v3.0")
        assert not ok

    def test_other_embedding_values_are_still_validated(self):
        assert validate_config_value("CGC_EMBEDDING_MODEL", "openai") == (True, None)
        assert not validate_config_value("CGC_EMBEDDING_MODEL", "bogus")[0]

    def test_litellm_model_and_base_are_known_keys(self):
        assert validate_config_value("LITELLM_MODEL", "anthropic/claude-sonnet-4-6") == (True, None)
        assert validate_config_value("LITELLM_API_BASE", "http://localhost:4000") == (True, None)
