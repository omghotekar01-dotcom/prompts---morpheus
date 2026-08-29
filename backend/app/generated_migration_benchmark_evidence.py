from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .generated_migration_benchmark import BENCHMARK_PROTOCOL, BENCHMARK_SCHEMA

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_STATES = {
    "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST",
    "MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST",
}


@dataclass(frozen=True)
class VerifiedGeneratedMigrationBenchmark:
    evidence_state: str
    source_candidate_id: str
    target_candidate_id: str
    repetitions: int
    rows: int
    total_reads: int
    manifest_hashes: tuple[str, str]


def _require_exact_int(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _require_hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 identity")
    if value == "0" * 64:
        raise ValueError(f"{name} must not be a placeholder hash")
    return value


def _require_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty canonical string")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name} contains control characters")
    return value


def verify_generated_migration_benchmark_evidence(report: Mapping[str, Any]) -> VerifiedGeneratedMigrationBenchmark:
    """Fail closed before generated-migration benchmark output is consumed as evidence.

    This verifies identity, row cardinality and invariants. It deliberately does not
    promote CI smoke measurements to publication-grade evidence.
    """
    if not isinstance(report, Mapping):
        raise ValueError("report must be an object")
    if report.get("schema") != BENCHMARK_SCHEMA:
        raise ValueError("unexpected benchmark schema")
    if report.get("protocol") != BENCHMARK_PROTOCOL:
        raise ValueError("unexpected benchmark protocol")
    if report.get("success") is not True:
        raise ValueError("benchmark must have succeeded")

    state = report.get("evidence_state")
    if state not in _ALLOWED_STATES:
        raise ValueError("unsupported generated migration benchmark evidence_state")

    source_candidate = _require_id(report.get("source_candidate_id"), "source_candidate_id")
    target_candidate = _require_id(report.get("target_candidate_id"), "target_candidate_id")
    if source_candidate == target_candidate:
        raise ValueError("source and target candidate identities must differ")

    for name in (
        "workload_ir_hash",
        "source_configuration_ir_hash",
        "target_configuration_ir_hash",
        "source_manifest_sha256",
        "target_manifest_sha256",
        "source_header_sha256",
        "target_header_sha256",
        "benchmark_source_sha256",
    ):
        _require_hash(report.get(name), name)

    config = report.get("config")
    if not isinstance(config, Mapping):
        raise ValueError("config must be an object")
    readers = _require_exact_int(config.get("readers"), "config.readers", minimum=1)
    transitions = _require_exact_int(config.get("transitions"), "config.transitions", minimum=1)
    repetitions = _require_exact_int(config.get("repetitions"), "config.repetitions", minimum=1)
    record_count = _require_exact_int(config.get("record_count"), "config.record_count", minimum=1)

    if report.get("compile_returncode") != 0 or report.get("run_returncode") != 0:
        raise ValueError("successful benchmark evidence requires zero compile/run return codes")

    rows = report.get("rows")
    if not isinstance(rows, list) or len(rows) != repetitions:
        raise ValueError("row count must equal configured repetitions")

    seen_repetitions: set[int] = set()
    total_reads = 0
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"rows[{index}] must be an object")
        repetition = _require_exact_int(row.get("repetition"), f"rows[{index}].repetition")
        if repetition in seen_repetitions:
            raise ValueError("duplicate repetition index")
        seen_repetitions.add(repetition)
        if row.get("readers") != readers or row.get("transitions") != transitions or row.get("record_count") != record_count:
            raise ValueError("row configuration does not match benchmark config")
        migrate_ns = _require_exact_int(row.get("migrate_validate_activate_ns_per"), f"rows[{index}].migrate_validate_activate_ns_per", minimum=1)
        rollback_ns = _require_exact_int(row.get("rollback_ns_per"), f"rows[{index}].rollback_ns_per", minimum=1)
        reads = _require_exact_int(row.get("reads"), f"rows[{index}].reads", minimum=1)
        invalid_reads = _require_exact_int(row.get("invalid_reads"), f"rows[{index}].invalid_reads")
        if invalid_reads != 0:
            raise ValueError("successful migration benchmark evidence cannot contain invalid reads")
        if not math.isfinite(float(migrate_ns)) or not math.isfinite(float(rollback_ns)):
            raise ValueError("timings must be finite")
        total_reads += reads

    if seen_repetitions != set(range(repetitions)):
        raise ValueError("repetition indexes must be contiguous from zero")

    return VerifiedGeneratedMigrationBenchmark(
        evidence_state=state,
        source_candidate_id=source_candidate,
        target_candidate_id=target_candidate,
        repetitions=repetitions,
        rows=len(rows),
        total_reads=total_reads,
        manifest_hashes=(report["source_manifest_sha256"], report["target_manifest_sha256"]),
    )
