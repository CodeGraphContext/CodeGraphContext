"""WireHintLoader: 4-source aggregation with precedence and union-merge (PR #2)."""

from pathlib import Path

import pytest

from codegraphcontext.wire import LoaderInputs, WireHintLoader, WireHintSource


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ── Empty inputs ─────────────────────────────────────────────────────────────

def test_loader_empty_inputs_yields_empty_set(tmp_path):
    loaded = WireHintLoader().load(LoaderInputs(env_var=""))
    assert loaded.is_empty()
    assert loaded.counts_by_source == {"cli": 0, "env": 0, "context": 0, "repo": 0}
    assert loaded.warnings == []


# ── Single-source cases ──────────────────────────────────────────────────────

def test_loader_cli_only(tmp_path):
    loaded = WireHintLoader().load(
        LoaderInputs(cli_hints=["kafka:orders=produced_by:pkg.Pub.publish"], env_var="")
    )
    assert loaded.counts_by_source["cli"] == 1
    assert loaded.topics[0].produced_by == ["pkg.Pub.publish"]
    assert loaded.topics[0].provenance[0].source is WireHintSource.CLI


def test_loader_env_only(tmp_path):
    env = "kafka:orders=consumed_by:pkg.Sub.consume\n"
    loaded = WireHintLoader().load(LoaderInputs(env_var=env))
    assert loaded.counts_by_source["env"] == 1
    assert loaded.topics[0].consumed_by == ["pkg.Sub.consume"]
    assert loaded.topics[0].provenance[0].source is WireHintSource.ENV


def test_loader_repo_only(tmp_path):
    _write(
        tmp_path / ".cgc" / "wire.yml",
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [pkg.P.pub]}\n",
    )
    loaded = WireHintLoader().load(LoaderInputs(env_var="", repo_paths=[tmp_path]))
    assert loaded.counts_by_source["repo"] == 1
    assert loaded.topics[0].produced_by == ["pkg.P.pub"]
    assert loaded.topics[0].provenance[0].source is WireHintSource.REPO
    assert loaded.topics[0].provenance[0].path.endswith("wire.yml")


def test_loader_context_only(tmp_path):
    ctx = _write(
        tmp_path / "ctx" / "wire.yml",
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [pkg.C.pub]}\n",
    )
    loaded = WireHintLoader().load(LoaderInputs(env_var="", context_hint_file=ctx))
    assert loaded.counts_by_source["context"] == 1
    assert loaded.topics[0].provenance[0].source is WireHintSource.CONTEXT


# ── Cross-source union: same wire node from multiple sources ─────────────────

def test_loader_unions_participants_across_sources(tmp_path):
    """
    Same topic (kafka:orders) declared in CLI, ENV, REPO, and CONTEXT.
    Producers/consumers from every source must land on a single Topic node.
    """
    _write(
        tmp_path / "repoA" / ".cgc" / "wire.yml",
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [pkg.Repo.pub]}\n",
    )
    ctx = _write(
        tmp_path / "ctx" / "wire.yml",
        "version: 1\ntopics:\n  - {system: kafka, name: orders, consumed_by: [pkg.Ctx.sub]}\n",
    )
    loaded = WireHintLoader().load(
        LoaderInputs(
            cli_hints=["kafka:orders=produced_by:pkg.Cli.pub"],
            env_var="kafka:orders=consumed_by:pkg.Env.sub\n",
            context_hint_file=ctx,
            repo_paths=[tmp_path / "repoA"],
        )
    )

    assert len(loaded.topics) == 1
    t = loaded.topics[0]
    assert set(t.produced_by) == {"pkg.Cli.pub", "pkg.Repo.pub"}
    assert set(t.consumed_by) == {"pkg.Env.sub", "pkg.Ctx.sub"}

    # Provenance carries every source that touched the node.
    sources = {p.source for p in t.provenance}
    assert sources == {
        WireHintSource.CLI, WireHintSource.ENV,
        WireHintSource.CONTEXT, WireHintSource.REPO,
    }


def test_loader_dedupes_repeated_participants(tmp_path):
    _write(
        tmp_path / ".cgc" / "wire.yml",
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [pkg.P.pub, pkg.P.pub]}\n",
    )
    loaded = WireHintLoader().load(
        LoaderInputs(
            cli_hints=["kafka:orders=produced_by:pkg.P.pub"],
            env_var="",
            repo_paths=[tmp_path],
        )
    )
    assert loaded.topics[0].produced_by == ["pkg.P.pub"]


def test_loader_disjoint_topics_all_present(tmp_path):
    _write(
        tmp_path / ".cgc" / "wire.yml",
        "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: [a.b.c]}\n",
    )
    loaded = WireHintLoader().load(
        LoaderInputs(
            cli_hints=["kafka:refunds=produced_by:x.y.z"],
            env_var="",
            repo_paths=[tmp_path],
        )
    )
    assert {t.name for t in loaded.topics} == {"orders", "refunds"}


# ── Robustness: bad inputs surface as warnings, don't crash ──────────────────

def test_loader_missing_repo_file_is_silent(tmp_path):
    loaded = WireHintLoader().load(LoaderInputs(env_var="", repo_paths=[tmp_path]))
    assert loaded.is_empty()
    assert loaded.warnings == []


def test_loader_missing_context_file_is_silent(tmp_path):
    loaded = WireHintLoader().load(
        LoaderInputs(env_var="", context_hint_file=tmp_path / "does-not-exist.yml")
    )
    assert loaded.is_empty()
    assert loaded.warnings == []


def test_loader_malformed_repo_file_warns_but_does_not_raise(tmp_path):
    _write(tmp_path / ".cgc" / "wire.yml", "version: 999\n")
    loaded = WireHintLoader().load(LoaderInputs(env_var="", repo_paths=[tmp_path]))
    assert loaded.is_empty()
    assert any("version" in w for w in loaded.warnings)


def test_loader_malformed_cli_hint_warns_but_does_not_raise(tmp_path):
    loaded = WireHintLoader().load(
        LoaderInputs(cli_hints=["not-a-valid-shorthand"], env_var="")
    )
    assert loaded.is_empty()
    assert loaded.warnings


def test_loader_warn_hook_is_called(tmp_path):
    seen = []
    loader = WireHintLoader(warn_hook=lambda msg, prov: seen.append((prov.source, msg)))
    loader.load(LoaderInputs(cli_hints=["broken"], env_var=""))
    assert seen and seen[0][0] is WireHintSource.CLI
