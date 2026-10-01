"""Walk a repo's Java sources and feed each to the Kafka extractor (MULTI_REPO_LINKS).

This module is the batch counterpart to :mod:`wire.kafka_extractor`. It walks
one or more source roots under a repo (default ``src/main/java``), reads each
``.java`` file, and aggregates the per-file :class:`KafkaExtractionResult`
into a single result for the whole repo.

Design points:

* We scope to conventional Maven / Gradle source roots by default so we do
  not accidentally scan generated code, third-party JARs unpacked into
  ``target/``, or test scaffolding. Callers can widen the scope with the
  ``include_dirs`` argument.
* We honour a per-file size cap identical to :mod:`wire.config_scanner`
  (default 512 KB) to bound worst-case memory when a repo has a
  machine-generated Java file.
* The scanner never writes to the graph — the caller (a later PR) decides
  whether to persist under ``MULTI_REPO_LINKS=true``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore
from codegraphcontext.wire.kafka_extractor import (
    KafkaConsumerRecord,
    KafkaExtractionResult,
    KafkaProducerRecord,
    extract_from_source,
    looks_like_kafka_source,
    scan_config_kafka_bindings,
)

DEFAULT_JAVA_SOURCE_DIRS: tuple = (
    "src/main/java",
    "src/main/kotlin",   # tolerated as a scan location, though the extractor is Java-only
    ".",                  # last resort — top-level standalone .java files
)

# Path substrings that mark files we never want to treat as production wire
# evidence. Test files pollute the extractor output with Mockito matchers,
# hard-coded fixture topic names, and stub RestTemplate calls that are not
# actual production couplings.
DEFAULT_JAVA_EXCLUDE_PATH_PARTS: tuple = (
    "/src/test/",
    "/src/testFixtures/",
    "/src/integrationTest/",
    "/src/it/",
)


def _is_excluded_java_path(path: Path, exclude_parts: Sequence[str]) -> bool:
    p = path.as_posix()
    return any(part in p for part in exclude_parts)


@dataclass
class KafkaScanResult:
    producers: List[KafkaProducerRecord] = field(default_factory=list)
    consumers: List[KafkaConsumerRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0

    def extend(self, per_file: KafkaExtractionResult) -> None:
        self.producers.extend(per_file.producers)
        self.consumers.extend(per_file.consumers)
        self.warnings.extend(per_file.warnings)


def scan_repo_kafka(
    repo_root: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
    include_dirs: Sequence[str] = DEFAULT_JAVA_SOURCE_DIRS,
    exclude_path_parts: Sequence[str] = DEFAULT_JAVA_EXCLUDE_PATH_PARTS,
    max_file_kb: int = 512,
) -> KafkaScanResult:
    """Walk ``repo_root`` and extract Kafka producer/consumer records from every ``.java`` file."""
    root = Path(repo_root).resolve()
    result = KafkaScanResult()

    seen: set = set()
    max_bytes = max_file_kb * 1024

    for rel in include_dirs:
        base = (root / rel).resolve()
        if not base.is_dir():
            continue
        # rglob is fine here — Java projects rarely have arbitrarily deep
        # symlink loops. The size cap defends against runaway inputs.
        for path in base.rglob("*.java"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if _is_excluded_java_path(resolved, exclude_path_parts):
                result.files_skipped += 1
                continue
            try:
                size = path.stat().st_size
            except OSError:
                result.files_skipped += 1
                continue
            if size > max_bytes:
                result.files_skipped += 1
                result.warnings.append(
                    f"{path}: skipped ({size / 1024:.1f} KB > {max_file_kb} KB cap)"
                )
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                result.files_skipped += 1
                result.warnings.append(f"{path}: read error: {e}")
                continue

            if not looks_like_kafka_source(text):
                # Not a Kafka file — count as scanned so the summary is honest.
                result.files_scanned += 1
                continue

            per_file = extract_from_source(
                text,
                path,
                store=store,
                active_profile=active_profile,
            )
            result.files_scanned += 1
            result.extend(per_file)

    # Config-driven registrations (no Java call site at all) — see
    # kafka_extractor.scan_config_kafka_bindings for the shape this covers.
    if store is not None:
        config_result = scan_config_kafka_bindings(store)
        result.extend(config_result)

    return result


__all__ = [
    "DEFAULT_JAVA_EXCLUDE_PATH_PARTS",
    "DEFAULT_JAVA_SOURCE_DIRS",
    "KafkaScanResult",
    "scan_repo_kafka",
]
