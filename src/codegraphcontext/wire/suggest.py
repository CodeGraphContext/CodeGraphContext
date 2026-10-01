"""Suggest likely cross-repo wire couplings from orphan wire records (MULTI_REPO_LINKS).

`cgc wire links` reports a topic/endpoint as "matched" only when a producer and a
consumer resolve to the exact same literal string. Two independently-configured
services routinely couple through *near*-identical identifiers instead — an
environment suffix (`order-events` vs `order-events_e2e`), a stray prefix, or
a minor spelling drift — and those pairs show up as two separate "orphan"
entries that never find each other, even though a human skimming both lists
would immediately spot the match.

This module re-ranks the orphan lists a human (or an agent) would otherwise
have to eyeball manually: it strips known environment-suffix patterns, scores
the remaining pairs by string similarity, and only proposes pairs that live in
*different* repos (a same-repo near-duplicate is not the cross-repo gap this
tool exists to surface). It never writes to the graph — the caller decides
whether to confirm a suggestion as a real `.cgc/wire.yml` hint.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

# Common environment/deployment-stage suffixes teams append to an otherwise
# shared identifier. Stripped repeatedly (so "topic_prod_e2e" -> "topic") before
# comparing two identifiers for a "same thing, different environment" match.
_ENV_SUFFIX_RE = re.compile(
    r"[-_](e2e|prod|production|prd|int|integration|dev|develop|qa|qadev|"
    r"lt|loadtest|stage|staging|test|uat|sandbox|local)$",
    re.IGNORECASE,
)

DEFAULT_MIN_SCORE = 0.6


def normalize_identifier(name: str) -> str:
    """Strip trailing environment-suffix segments repeatedly, e.g. `x_prod_e2e` -> `x`."""
    current = name
    while True:
        stripped = _ENV_SUFFIX_RE.sub("", current)
        if stripped == current:
            return current
        current = stripped


def similarity(a: str, b: str) -> float:
    """Similarity ratio in [0, 1]; 1.0 means identical strings."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def repo_for_path(path: str, repo_roots: Sequence[str]) -> Optional[str]:
    """Return the configured repo root that ``path`` lives under, or None.

    Picks the longest (most specific) matching root when repo roots nest.
    """
    best: Optional[str] = None
    for root in repo_roots:
        root_norm = root.rstrip("/")
        if path == root_norm or path.startswith(root_norm + "/"):
            if best is None or len(root_norm) > len(best):
                best = root_norm
    return best


def _repo_examples(paths: Sequence[str], repo_roots: Sequence[str]) -> Dict[str, str]:
    """Return {repo_root: one_example_path} for every distinct repo represented in ``paths``."""
    out: Dict[str, str] = {}
    for p in paths:
        repo = repo_for_path(p, repo_roots) or "?"
        out.setdefault(repo, p)
    return out


@dataclass(frozen=True)
class WireCandidate:
    kind: str              # "kafka" | "http" | "grpc"
    left_repo: str
    left_name: str          # topic name, or "protocol method path" for endpoints
    left_location: str
    right_repo: str
    right_name: str
    right_location: str
    score: float             # 0..1, 1.0 = identical after normalization
    reason: str               # "exact-after-normalization" | "fuzzy"


def _score_pair(left_raw: str, right_raw: str) -> tuple:
    """Return (score, reason) for two raw identifiers, preferring the normalized match."""
    if left_raw == right_raw:
        # Already handled by `cgc wire links` — not an orphan pairing worth suggesting.
        return 0.0, ""
    left_norm = normalize_identifier(left_raw)
    right_norm = normalize_identifier(right_raw)
    if left_norm and left_norm == right_norm:
        return 1.0, "exact-after-normalization"
    return similarity(left_norm, right_norm), "fuzzy"


def suggest_topic_pairs(
    orphan_producers: Sequence[dict],
    orphan_consumers: Sequence[dict],
    repo_roots: Sequence[str],
    *,
    min_score: float = DEFAULT_MIN_SCORE,
) -> List[WireCandidate]:
    """Rank candidate cross-repo Kafka topic pairs.

    Each input dict is shaped like the `wire links` orphan rows:
    ``{"name": <topic name>, "locations": [<path>, ...]}``.
    """
    candidates: List[WireCandidate] = []
    for p in orphan_producers:
        for c in orphan_consumers:
            score, reason = _score_pair(p["name"], c["name"])
            if score < min_score:
                continue
            p_examples = _repo_examples(p.get("locations") or [], repo_roots)
            c_examples = _repo_examples(c.get("locations") or [], repo_roots)
            for p_repo, p_loc in p_examples.items():
                for c_repo, c_loc in c_examples.items():
                    if p_repo == c_repo:
                        continue
                    candidates.append(WireCandidate(
                        kind="kafka",
                        left_repo=p_repo, left_name=p["name"], left_location=p_loc,
                        right_repo=c_repo, right_name=c["name"], right_location=c_loc,
                        score=score, reason=reason,
                    ))
    candidates.sort(key=lambda c: -c.score)
    return candidates


def suggest_endpoint_pairs(
    orphan_servers: Sequence[dict],
    orphan_clients: Sequence[dict],
    repo_roots: Sequence[str],
    *,
    min_score: float = DEFAULT_MIN_SCORE,
) -> List[WireCandidate]:
    """Rank candidate cross-repo HTTP/gRPC endpoint pairs.

    Each input dict is shaped like the `wire links` orphan rows:
    ``{"protocol": ..., "method": ..., "path": ..., "locations": [<path>, ...]}``.
    Only same-protocol pairs are compared.
    """
    candidates: List[WireCandidate] = []
    for s in orphan_servers:
        s_id = f"{s['method']} {s['path']}"
        for c in orphan_clients:
            if s.get("protocol") != c.get("protocol"):
                continue
            c_id = f"{c['method']} {c['path']}"
            score, reason = _score_pair(s_id, c_id)
            if score < min_score:
                continue
            s_examples = _repo_examples(s.get("locations") or [], repo_roots)
            c_examples = _repo_examples(c.get("locations") or [], repo_roots)
            for s_repo, s_loc in s_examples.items():
                for c_repo, c_loc in c_examples.items():
                    if s_repo == c_repo:
                        continue
                    candidates.append(WireCandidate(
                        kind=s.get("protocol", "http"),
                        left_repo=s_repo, left_name=s_id, left_location=s_loc,
                        right_repo=c_repo, right_name=c_id, right_location=c_loc,
                        score=score, reason=reason,
                    ))
    candidates.sort(key=lambda c: -c.score)
    return candidates


__all__ = [
    "DEFAULT_MIN_SCORE",
    "WireCandidate",
    "normalize_identifier",
    "repo_for_path",
    "similarity",
    "suggest_endpoint_pairs",
    "suggest_topic_pairs",
]
