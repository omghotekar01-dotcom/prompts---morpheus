from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

_HEX = set("0123456789abcdef")


def _sha256(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in _HEX for ch in normalized):
        raise ValueError(f"{field} must be a lowercase-compatible SHA-256 hex digest")
    return normalized


def _utc(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class ReproductionAttestation:
    schema: str
    source_revision: str
    reproduction_pack_sha256: str
    environment_sha256: str
    workload_sha256: str
    results_sha256: str
    commands_sha256: str
    verifier_ids: tuple[str, ...]
    verified_at: str
    attestation_sha256: str


def build_reproduction_attestation(
    *,
    source_revision: str,
    reproduction_pack_sha256: str,
    environment_sha256: str,
    workload_sha256: str,
    results_sha256: str,
    commands_sha256: str,
    verifier_ids: Sequence[str],
    verified_at: str,
) -> ReproductionAttestation:
    if not isinstance(source_revision, str) or len(source_revision.strip()) != 40 or any(
        ch not in _HEX for ch in source_revision.strip().lower()
    ):
        raise ValueError("source_revision must be a full 40-character Git SHA-1")

    verifiers = tuple(sorted({str(v).strip() for v in verifier_ids if str(v).strip()}))
    if not verifiers:
        raise ValueError("at least one independent verifier_id is required")

    hashes = {
        "reproduction_pack_sha256": _sha256(reproduction_pack_sha256, "reproduction_pack_sha256"),
        "environment_sha256": _sha256(environment_sha256, "environment_sha256"),
        "workload_sha256": _sha256(workload_sha256, "workload_sha256"),
        "results_sha256": _sha256(results_sha256, "results_sha256"),
        "commands_sha256": _sha256(commands_sha256, "commands_sha256"),
    }
    if len(set(hashes.values())) != len(hashes):
        raise ValueError("reproduction evidence identities must be distinct")

    payload = {
        "schema": "morpheus.reproduction_attestation.v1",
        "source_revision": source_revision.strip().lower(),
        **hashes,
        "verifier_ids": list(verifiers),
        "verified_at": _utc(verified_at, "verified_at"),
    }
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    return ReproductionAttestation(**payload, attestation_sha256=digest)


def verify_reproduction_attestation(attestation: ReproductionAttestation) -> bool:
    rebuilt = build_reproduction_attestation(
        source_revision=attestation.source_revision,
        reproduction_pack_sha256=attestation.reproduction_pack_sha256,
        environment_sha256=attestation.environment_sha256,
        workload_sha256=attestation.workload_sha256,
        results_sha256=attestation.results_sha256,
        commands_sha256=attestation.commands_sha256,
        verifier_ids=attestation.verifier_ids,
        verified_at=attestation.verified_at,
    )
    return hashlib.compare_digest(rebuilt.attestation_sha256, _sha256(attestation.attestation_sha256, "attestation_sha256"))
