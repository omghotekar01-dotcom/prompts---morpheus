from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .generated_migration_benchmark_evidence import verify_generated_migration_benchmark_evidence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MigrationCampaignPromotion:
    promoted: bool
    evidence_state: str
    source_candidate_id: str
    target_candidate_id: str
    independent_reports: int
    total_repetitions: int
    total_reads: int
    benchmark_source_sha256: str
    report_sha256: tuple[str, ...]
    decision_sha256: str


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def promote_generated_migration_campaign(
    reports: Sequence[Mapping[str, Any]],
    *,
    minimum_independent_reports: int = 3,
) -> MigrationCampaignPromotion:
    """Promote repeated generated-migration measurements into campaign evidence.

    A single successful benchmark is deliberately insufficient. Promotion requires
    multiple independently hash-bound reports for the same source/target pair while
    keeping the benchmark implementation itself fixed as a controlled experimental
    variable. This gate establishes evidence sufficiency only; it does not make a
    publication claim.
    """
    if isinstance(minimum_independent_reports, bool) or not isinstance(minimum_independent_reports, int):
        raise ValueError("minimum_independent_reports must be an integer")
    if minimum_independent_reports < 3:
        raise ValueError("minimum_independent_reports must be >= 3")
    if not isinstance(reports, Sequence) or isinstance(reports, (str, bytes, bytearray)):
        raise ValueError("reports must be a sequence")
    if len(reports) < minimum_independent_reports:
        raise ValueError("insufficient independent generated-migration reports")

    verified = []
    report_hashes: list[str] = []
    manifest_pairs: set[tuple[str, str]] = set()
    benchmark_source_identity: str | None = None

    for index, report in enumerate(reports):
        if not isinstance(report, Mapping):
            raise ValueError(f"reports[{index}] must be an object")
        item = verify_generated_migration_benchmark_evidence(report)
        verified.append(item)

        report_hash = _canonical_sha256(report)
        if report_hash in report_hashes:
            raise ValueError("duplicate generated-migration report evidence")
        report_hashes.append(report_hash)

        manifest_pair = item.manifest_hashes
        if manifest_pair in manifest_pairs:
            raise ValueError("source/target manifest pair reused across supposedly independent reports")
        manifest_pairs.add(manifest_pair)

        benchmark_source = report.get("benchmark_source_sha256")
        if not isinstance(benchmark_source, str) or not _SHA256.fullmatch(benchmark_source) or benchmark_source == "0" * 64:
            raise ValueError("benchmark_source_sha256 must be a non-placeholder lowercase SHA-256 identity")
        if benchmark_source_identity is None:
            benchmark_source_identity = benchmark_source
        elif benchmark_source != benchmark_source_identity:
            raise ValueError("campaign reports must use one controlled benchmark source identity")

    first = verified[0]
    for item in verified[1:]:
        if item.source_candidate_id != first.source_candidate_id or item.target_candidate_id != first.target_candidate_id:
            raise ValueError("all campaign reports must measure the same source/target candidate pair")
        if item.evidence_state != first.evidence_state:
            raise ValueError("campaign reports must use one evidence_state")

    assert benchmark_source_identity is not None
    decision_payload = {
        "schema": "morpheus.generated_migration_campaign_promotion.v2",
        "promoted": True,
        "evidence_state": first.evidence_state,
        "source_candidate_id": first.source_candidate_id,
        "target_candidate_id": first.target_candidate_id,
        "minimum_independent_reports": minimum_independent_reports,
        "independent_reports": len(verified),
        "total_repetitions": sum(item.repetitions for item in verified),
        "total_reads": sum(item.total_reads for item in verified),
        "benchmark_source_sha256": benchmark_source_identity,
        "report_sha256": sorted(report_hashes),
        "manifest_pairs": sorted([list(pair) for pair in manifest_pairs]),
    }
    decision_sha256 = _canonical_sha256(decision_payload)

    return MigrationCampaignPromotion(
        promoted=True,
        evidence_state=first.evidence_state,
        source_candidate_id=first.source_candidate_id,
        target_candidate_id=first.target_candidate_id,
        independent_reports=len(verified),
        total_repetitions=decision_payload["total_repetitions"],
        total_reads=decision_payload["total_reads"],
        benchmark_source_sha256=benchmark_source_identity,
        report_sha256=tuple(decision_payload["report_sha256"]),
        decision_sha256=decision_sha256,
    )
