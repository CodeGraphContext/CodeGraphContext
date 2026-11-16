"""WireHintLoader: aggregate hints from CLI, ENV, context config, and repo files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from codegraphcontext.wire.hints import (
    LoadedHintSet,
    WireAlias,
    WireEndpointHint,
    WireHintFile,
    WireHintSource,
    WireHintValidationError,
    WireProvenance,
    WireTopicHint,
)
from codegraphcontext.wire.parser import (
    parse_cli_hints,
    parse_env_hints,
    parse_wire_file,
)

# Canonical location of a wire hint file inside a repo or context directory.
WIRE_HINT_FILENAME = "wire.yml"
REPO_HINT_SUBDIR = ".cgc"
ENV_VAR_NAME = "CGC_WIRE"


@dataclass
class LoaderInputs:
    """All inputs the loader considers. `None` fields mean 'source disabled'."""
    cli_hints: Optional[Sequence[str]] = None                  # CLI shorthand strings
    env_var: Optional[str] = None                              # raw CGC_WIRE value; None = read os.environ
    context_hint_file: Optional[Path] = None                   # context-scoped wire.yml
    repo_paths: Optional[Sequence[Path]] = None                # repo roots to scan for .cgc/wire.yml


class WireHintLoader:
    """Load and merge wire hints from all four sources.

    Precedence for provenance labeling is CLI > ENV > CONTEXT > REPO. Content
    is merged by unioning the participant lists on matching wire nodes — no
    source "wins" and silently discards another. When the same wire node
    appears in multiple sources, every source shows up in its provenance list,
    which is what `cgc wire list` reports.
    """

    def __init__(self, *, warn_hook=None) -> None:
        # Callback signature: (message: str, provenance: WireProvenance) -> None.
        # Kept as a hook so the future pipeline can route these into
        # IndexWarning nodes without the loader knowing about the graph.
        self._warn_hook = warn_hook

    def load(self, inputs: LoaderInputs) -> LoadedHintSet:
        files: List[WireHintFile] = []
        counts: Dict[str, int] = {s.value: 0 for s in WireHintSource}
        warnings: List[str] = []

        # 1) CLI — highest precedence.
        cli_files = self._safe(parse_cli_hints, inputs.cli_hints or [], warnings)
        counts[WireHintSource.CLI.value] = _count_hints(cli_files)
        files.extend(cli_files)

        # 2) ENV.
        env_text = inputs.env_var if inputs.env_var is not None else os.environ.get(ENV_VAR_NAME)
        env_files = self._safe(parse_env_hints, env_text, warnings)
        counts[WireHintSource.ENV.value] = _count_hints(env_files)
        files.extend(env_files)

        # 3) Context-scoped hint file.
        if inputs.context_hint_file and Path(inputs.context_hint_file).is_file():
            f = self._safe_file(inputs.context_hint_file, WireHintSource.CONTEXT, warnings)
            if f is not None:
                counts[WireHintSource.CONTEXT.value] = _count_hints([f])
                files.append(f)

        # 4) Repo-scoped hint files.
        repo_count = 0
        for repo in inputs.repo_paths or []:
            hint_path = Path(repo) / REPO_HINT_SUBDIR / WIRE_HINT_FILENAME
            if not hint_path.is_file():
                continue
            f = self._safe_file(hint_path, WireHintSource.REPO, warnings)
            if f is not None:
                repo_count += _count_hints([f])
                files.append(f)
        counts[WireHintSource.REPO.value] = repo_count

        merged_topics, merged_endpoints, merged_aliases = _merge_files(files)
        # Roll up per-file warnings after the merge so callers see everything.
        for f in files:
            warnings.extend(f.warnings)

        return LoadedHintSet(
            topics=merged_topics,
            endpoints=merged_endpoints,
            aliases=merged_aliases,
            counts_by_source=counts,
            warnings=warnings,
        )

    # ── internal helpers ────────────────────────────────────────────────────

    def _safe(self, fn, arg, warnings: List[str]):
        try:
            return fn(arg)
        except WireHintValidationError as e:
            warnings.append(str(e))
            if self._warn_hook:
                self._warn_hook(str(e), WireProvenance(source=WireHintSource.CLI))
            return []

    def _safe_file(
        self, path: Path, source: WireHintSource, warnings: List[str]
    ) -> Optional[WireHintFile]:
        try:
            return parse_wire_file(Path(path), source=source)
        except WireHintValidationError as e:
            msg = f"{path}: {e}"
            warnings.append(msg)
            if self._warn_hook:
                self._warn_hook(msg, WireProvenance(source=source, path=str(path)))
            return None
        except OSError as e:
            msg = f"{path}: {e}"
            warnings.append(msg)
            return None


# ── merging ──────────────────────────────────────────────────────────────────

def _merge_files(
    files: Iterable[WireHintFile],
) -> tuple[List[WireTopicHint], List[WireEndpointHint], List[WireAlias]]:
    """Union participants for matching wire identities across every source."""
    topics: Dict[tuple, WireTopicHint] = {}
    endpoints: Dict[tuple, WireEndpointHint] = {}
    aliases: Dict[tuple, WireAlias] = {}

    for f in files:
        for t in f.topics:
            key = t.merge_key()
            existing = topics.get(key)
            if existing is None:
                topics[key] = WireTopicHint(
                    system=t.system,
                    name=t.name,
                    produced_by=list(t.produced_by),
                    consumed_by=list(t.consumed_by),
                    provenance=list(t.provenance),
                )
            else:
                _extend_unique(existing.produced_by, t.produced_by)
                _extend_unique(existing.consumed_by, t.consumed_by)
                existing.provenance.extend(t.provenance)

        for e in f.endpoints:
            key = e.merge_key()
            existing_e = endpoints.get(key)
            if existing_e is None:
                endpoints[key] = WireEndpointHint(
                    protocol=e.protocol,
                    method=e.method,
                    path=e.path,
                    served_by=list(e.served_by),
                    invoked_by=list(e.invoked_by),
                    provenance=list(e.provenance),
                )
            else:
                _extend_unique(existing_e.served_by, e.served_by)
                _extend_unique(existing_e.invoked_by, e.invoked_by)
                existing_e.provenance.extend(e.provenance)

        for a in f.aliases:
            key = (a.kind, a.canonical)
            existing_a = aliases.get(key)
            if existing_a is None:
                aliases[key] = WireAlias(
                    kind=a.kind,
                    canonical=a.canonical,
                    aliases=list(a.aliases),
                    provenance=list(a.provenance),
                )
            else:
                _extend_unique(existing_a.aliases, a.aliases)
                existing_a.provenance.extend(a.provenance)

    return list(topics.values()), list(endpoints.values()), list(aliases.values())


def _extend_unique(target: List[str], incoming: Iterable[str]) -> None:
    seen = set(target)
    for x in incoming:
        if x not in seen:
            target.append(x)
            seen.add(x)


def _count_hints(files: Iterable[WireHintFile]) -> int:
    n = 0
    for f in files:
        n += len(f.topics) + len(f.endpoints) + len(f.aliases)
    return n
