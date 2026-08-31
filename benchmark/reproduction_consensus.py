from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable

from reproduction_attestation import ReproductionAttestation, verify_reproduction_attestation

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ReproductionConsensus:
    source_revision: str
    workload_sha256: str
    results_sha256: str
    attestation_sha256s: tuple[str, ...]
    verifier_ids: tuple[str, ...]
    independent_lab_count: int
    required_lab_count: int
    consensus_sha256: str


def _canonical_payload(consensus: ReproductionConsensus) -> bytes:
    payload = {
        "source_revision": consensus.source_revision,
        "workload_sha256": consensus.workload_sha256,
        "results_sha256": consensus.results_sha256,
        "attestation_sha256s": list(consensus.attestation_sha256s),
        "verifier_ids": list(consensus.verifier_ids),
        "independent_lab_count": consensus.independent_lab_count,
        "required_lab_count": consensus.required_lab_count,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_reproduction_consensus(
    attestations: Iterable[ReproductionAttestation], *, required_lab_count: int = 2
) -> ReproductionConsensus:
    if isinstance(required_lab_count, bool) or required_lab_count < 2:
        raise ValueError("required_lab_count must be an integer >= 2")

    items = tuple(attestations)
    if len(items) < required_lab_count:
        raise ValueError("not enough attestations for independent reproduction consensus")
    if not all(verify_reproduction_attestation(item) for item in items):
        raise ValueError("all reproduction attestations must verify")

    source_revisions = {item.source_revision for item in items}
    workload_hashes = {item.workload_sha256 for item in items}
    results_hashes = {item.results_sha256 for item in items}
    if len(source_revisions) != 1 or len(workload_hashes) != 1 or len(results_hashes) != 1:
        raise ValueError("attestations disagree on source/workload/results lineage")

    attestation_hashes = tuple(sorted(item.attestation_sha256 for item in items))
    if len(set(attestation_hashes)) != len(attestation_hashes):
        raise ValueError("duplicate attestation evidence is not independent reproduction")

    verifier_groups = [set(item.verifier_ids) for item in items]
    if any(not group for group in verifier_groups):
        raise ValueError("each attestation must name at least one verifier")
    for index, left in enumerate(verifier_groups):
        for right in verifier_groups[index + 1 :]:
            if left & right:
                raise ValueError("independent reproduction attestations must not share verifier ids")

    verifier_ids = tuple(sorted({verifier for group in verifier_groups for verifier in group}))
    consensus = ReproductionConsensus(
        source_revision=items[0].source_revision,
        workload_sha256=items[0].workload_sha256,
        results_sha256=items[0].results_sha256,
        attestation_sha256s=attestation_hashes,
        verifier_ids=verifier_ids,
        independent_lab_count=len(items),
        required_lab_count=required_lab_count,
        consensus_sha256="",
    )
    digest = sha256(_canonical_payload(consensus)).hexdigest()
    return ReproductionConsensus(**{**consensus.__dict__, "consensus_sha256": digest})


def verify_reproduction_consensus(consensus: ReproductionConsensus) -> bool:
    if not _GIT_SHA.fullmatch(consensus.source_revision):
        return False
    if not _SHA256.fullmatch(consensus.workload_sha256) or not _SHA256.fullmatch(consensus.results_sha256):
        return False
    if isinstance(consensus.required_lab_count, bool) or consensus.required_lab_count < 2:
        return False
    if consensus.independent_lab_count < consensus.required_lab_count:
        return False
    if len(consensus.attestation_sha256s) != consensus.independent_lab_count:
        return False
    if len(set(consensus.attestation_sha256s)) != len(consensus.attestation_sha256s):
        return False
    if any(not _SHA256.fullmatch(value) for value in consensus.attestation_sha256s):
        return False
    if tuple(sorted(consensus.attestation_sha256s)) != consensus.attestation_sha256s:
        return False
    if tuple(sorted(set(consensus.verifier_ids))) != consensus.verifier_ids:
        return False
    expected = sha256(_canonical_payload(consensus)).hexdigest()
    return expected == consensus.consensus_sha256
