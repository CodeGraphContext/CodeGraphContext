#!/usr/bin/env python3
"""Compare Neo4j vs KuzuDB snapshot outputs for CGC commands.

Usage examples:
  python scripts/compare_backend_snapshots.py
  python scripts/compare_backend_snapshots.py --lowercase
  python scripts/compare_backend_snapshots.py \
    --neo-callers neo4j_callers.txt --kuzu-callers kuzu_callers.txt \
    --neo-deps neo4j_deps.json --kuzu-deps kuzu_deps.json \
    --neo-content neo4j_content.txt --kuzu-content kuzu_content.txt
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def normalize_whitespace(text: str) -> str:
    return " ".join(text.strip().split())


def normalize_line(line: str, lowercase: bool) -> str:
    value = normalize_whitespace(line)
    if lowercase:
        value = value.lower()
    return value


def load_text_lines(path: Path, lowercase: bool) -> Tuple[List[str], Counter]:
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    normalized = [normalize_line(line, lowercase) for line in raw]
    normalized = [line for line in normalized if line]
    return normalized, Counter(normalized)


def normalize_json(value: Any) -> Any:
    """Normalize JSON recursively while ignoring ordering differences.

    - dict keys are sorted by name
    - lists are normalized and then sorted by canonical JSON representation
    """
    if isinstance(value, dict):
        return {k: normalize_json(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        items = [normalize_json(v) for v in value]
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return {}
    return json.loads(text)


def jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    union = a | b
    if not union:
        return 100.0
    return (len(a & b) / len(union)) * 100.0


def compare_text(neo_path: Path, kuzu_path: Path, lowercase: bool) -> Dict[str, Any]:
    neo_lines, neo_counts = load_text_lines(neo_path, lowercase)
    kuzu_lines, kuzu_counts = load_text_lines(kuzu_path, lowercase)

    neo_set = set(neo_lines)
    kuzu_set = set(kuzu_lines)

    missing_in_kuzu = sorted(neo_set - kuzu_set)
    extra_in_kuzu = sorted(kuzu_set - neo_set)
    duplicates_in_kuzu = sorted([line for line, c in kuzu_counts.items() if c > 1])

    return {
        "neo_total_lines": len(neo_lines),
        "kuzu_total_lines": len(kuzu_lines),
        "neo_unique": len(neo_set),
        "kuzu_unique": len(kuzu_set),
        "missing_in_kuzu": missing_in_kuzu,
        "extra_in_kuzu": extra_in_kuzu,
        "duplicates_in_kuzu": duplicates_in_kuzu,
        "similarity_percent": jaccard_similarity(neo_set, kuzu_set),
    }


def compare_lists(path: str, neo_list: List[Any], kuzu_list: List[Any]) -> Dict[str, Any]:
    neo_items = [canonical_json(normalize_json(v)) for v in neo_list]
    kuzu_items = [canonical_json(normalize_json(v)) for v in kuzu_list]

    neo_set = set(neo_items)
    kuzu_set = set(kuzu_items)

    return {
        "path": path,
        "missing_in_kuzu": sorted(neo_set - kuzu_set),
        "extra_in_kuzu": sorted(kuzu_set - neo_set),
        "neo_count": len(neo_list),
        "kuzu_count": len(kuzu_list),
        "neo_unique": len(neo_set),
        "kuzu_unique": len(kuzu_set),
    }


def compare_json_recursive(neo: Any, kuzu: Any, path: str = "$") -> Dict[str, List[Any]]:
    missing_entries: List[Dict[str, Any]] = []
    extra_entries: List[Dict[str, Any]] = []
    value_differences: List[Dict[str, Any]] = []

    if isinstance(neo, dict) and isinstance(kuzu, dict):
        neo_keys = set(neo.keys())
        kuzu_keys = set(kuzu.keys())

        for key in sorted(neo_keys - kuzu_keys):
            missing_entries.append({"path": f"{path}.{key}", "value": neo[key]})

        for key in sorted(kuzu_keys - neo_keys):
            extra_entries.append({"path": f"{path}.{key}", "value": kuzu[key]})

        for key in sorted(neo_keys & kuzu_keys):
            child = compare_json_recursive(neo[key], kuzu[key], f"{path}.{key}")
            missing_entries.extend(child["missing_entries"])
            extra_entries.extend(child["extra_entries"])
            value_differences.extend(child["value_differences"])

        return {
            "missing_entries": missing_entries,
            "extra_entries": extra_entries,
            "value_differences": value_differences,
        }

    if isinstance(neo, list) and isinstance(kuzu, list):
        list_cmp = compare_lists(path, neo, kuzu)
        if list_cmp["missing_in_kuzu"]:
            missing_entries.append({
                "path": path,
                "count": len(list_cmp["missing_in_kuzu"]),
                "items": list_cmp["missing_in_kuzu"],
            })
        if list_cmp["extra_in_kuzu"]:
            extra_entries.append({
                "path": path,
                "count": len(list_cmp["extra_in_kuzu"]),
                "items": list_cmp["extra_in_kuzu"],
            })
        return {
            "missing_entries": missing_entries,
            "extra_entries": extra_entries,
            "value_differences": value_differences,
        }

    n = normalize_json(neo)
    k = normalize_json(kuzu)
    if n != k:
        value_differences.append({"path": path, "neo4j": n, "kuzudb": k})

    return {
        "missing_entries": missing_entries,
        "extra_entries": extra_entries,
        "value_differences": value_differences,
    }


def extract_entities(obj: Any, path: str = "$", out: Set[str] | None = None) -> Set[str]:
    if out is None:
        out = set()

    if isinstance(obj, dict):
        for k in sorted(obj.keys()):
            extract_entities(obj[k], f"{path}.{k}", out)
    elif isinstance(obj, list):
        for item in obj:
            out.add(f"{path}[]::{canonical_json(normalize_json(item))}")
    else:
        out.add(f"{path}={canonical_json(obj)}")
    return out


@dataclass
class SeveritySummary:
    critical: List[str]
    minor: List[str]


def classify_severity(callers: Dict[str, Any], deps: Dict[str, Any], content: Dict[str, Any]) -> SeveritySummary:
    critical: List[str] = []
    minor: List[str] = []

    if callers["missing_in_kuzu"]:
        critical.append(f"CALLERS missing relationships: {len(callers['missing_in_kuzu'])}")
    if deps["missing_entries"] or deps["value_differences"]:
        critical.append(
            "DEPS graph mismatch: "
            f"missing={len(deps['missing_entries'])}, value_diffs={len(deps['value_differences'])}"
        )

    if callers["extra_in_kuzu"]:
        minor.append(f"CALLERS extra relationships in Kuzu: {len(callers['extra_in_kuzu'])}")
    if content["duplicates_in_kuzu"]:
        minor.append(f"CONTENT duplicate entries in Kuzu: {len(content['duplicates_in_kuzu'])}")
    if content["extra_in_kuzu"]:
        minor.append(f"CONTENT extra matches in Kuzu: {len(content['extra_in_kuzu'])}")
    if deps["extra_entries"]:
        minor.append(f"DEPS extra entries in Kuzu: {len(deps['extra_entries'])}")

    return SeveritySummary(critical=critical, minor=minor)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Neo4j and KuzuDB CGC outputs.")
    parser.add_argument("--neo-callers", default="neo4j_callers.txt")
    parser.add_argument("--kuzu-callers", default="kuzu_callers.txt")
    parser.add_argument("--neo-deps", default="neo4j_deps.json")
    parser.add_argument("--kuzu-deps", default="kuzu_deps.json")
    parser.add_argument("--neo-content", default="neo4j_content.txt")
    parser.add_argument("--kuzu-content", default="kuzu_content.txt")
    parser.add_argument("--lowercase", action="store_true", help="Lowercase text lines before comparison.")
    parser.add_argument("--max-items", type=int, default=25, help="Max items to print per difference bucket.")
    return parser.parse_args()


def ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")


def print_list(label: str, items: List[Any], max_items: int) -> None:
    print(f"{label}: {len(items)}")
    for item in items[:max_items]:
        print(f"  - {item}")
    if len(items) > max_items:
        print(f"  ... ({len(items) - max_items} more)")


def main() -> None:
    args = parse_args()

    neo_callers_path = Path(args.neo_callers)
    kuzu_callers_path = Path(args.kuzu_callers)
    neo_deps_path = Path(args.neo_deps)
    kuzu_deps_path = Path(args.kuzu_deps)
    neo_content_path = Path(args.neo_content)
    kuzu_content_path = Path(args.kuzu_content)

    for p in [
        neo_callers_path,
        kuzu_callers_path,
        neo_deps_path,
        kuzu_deps_path,
        neo_content_path,
        kuzu_content_path,
    ]:
        ensure_exists(p)

    callers_cmp = compare_text(neo_callers_path, kuzu_callers_path, lowercase=args.lowercase)
    content_cmp = compare_text(neo_content_path, kuzu_content_path, lowercase=args.lowercase)

    neo_deps = load_json(neo_deps_path)
    kuzu_deps = load_json(kuzu_deps_path)
    deps_cmp = compare_json_recursive(neo_deps, kuzu_deps)

    deps_entities_neo = extract_entities(neo_deps)
    deps_entities_kuzu = extract_entities(kuzu_deps)
    deps_similarity = jaccard_similarity(deps_entities_neo, deps_entities_kuzu)

    severity = classify_severity(callers_cmp, deps_cmp, content_cmp)

    print("=== CALLERS ===")
    print(f"Neo4j unique: {callers_cmp['neo_unique']}")
    print(f"Kuzu unique: {callers_cmp['kuzu_unique']}")
    print(f"Similarity: {callers_cmp['similarity_percent']:.2f}%")
    print_list("Missing in Kuzu", callers_cmp["missing_in_kuzu"], args.max_items)
    print_list("Extra in Kuzu", callers_cmp["extra_in_kuzu"], args.max_items)
    print()

    print("=== DEPS ===")
    print(f"Similarity: {deps_similarity:.2f}%")
    print_list("Missing entries in Kuzu", deps_cmp["missing_entries"], args.max_items)
    print_list("Extra entries in Kuzu", deps_cmp["extra_entries"], args.max_items)
    print_list("Value differences", deps_cmp["value_differences"], args.max_items)
    print()

    print("=== CONTENT ===")
    print(f"Neo4j unique: {content_cmp['neo_unique']}")
    print(f"Kuzu unique: {content_cmp['kuzu_unique']}")
    print(f"Similarity: {content_cmp['similarity_percent']:.2f}%")
    print_list("Duplicate entries in Kuzu", content_cmp["duplicates_in_kuzu"], args.max_items)
    print_list("Missing matches in Kuzu", content_cmp["missing_in_kuzu"], args.max_items)
    print_list("Extra matches in Kuzu", content_cmp["extra_in_kuzu"], args.max_items)
    print()

    print("=== SEVERITY SUMMARY ===")
    print_list("Critical", severity.critical, args.max_items)
    print_list("Minor", severity.minor, args.max_items)


if __name__ == "__main__":
    main()
