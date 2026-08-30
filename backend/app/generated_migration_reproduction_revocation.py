from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_REASONS = {
    "archive_retracted",
    "publication_retracted",
    "reproduction_evidence_invalidated",
    "policy_violation",
    "runner_environment_compromised",
}


@dataclass(frozen=True)
class MigrationReproductionRevocation:
    schema: str
    attestation_sha256: str
    reason: str
    evidence_sha256s: tuple[str, ...]
    predecessor_revocation_sha256: str | None
    revoked: bool
    revocation_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def revoke_generated_migration_reproduction(
    *,
    attestation: Any,
    reason: str,
    evidence_sha256s: Sequence[str],
    predecessor_revocation_sha256: str | None = None,
) -> MigrationReproductionRevocation:
    if getattr(attestation, "reproduction_verified", None) is not True:
        raise ValueError("attestation must be explicitly reproduction-verified")
    attestation_id = _hash(getattr(attestation, "attestation_sha256", None), "attestation.attestation_sha256")
    if reason not in _ALLOWED_REASONS:
        raise ValueError("unsupported revocation reason")
    evidence = tuple(sorted(_hash(value, "evidence_sha256s") for value in evidence_sha256s))
    if not evidence:
        raise ValueError("at least one independent revocation evidence identity is required")
    if len(set(evidence)) != len(evidence):
        raise ValueError("revocation evidence identities must be unique")
    predecessor = None if predecessor_revocation_sha256 is None else _hash(predecessor_revocation_sha256, "predecessor_revocation_sha256")
    identities = [attestation_id, *evidence]
    if predecessor is not None:
        identities.append(predecessor)
    if len(set(identities)) != len(identities):
        raise ValueError("revocation identities must be independent")
    payload = {
        "schema": "morpheus.generated_migration_reproduction_revocation.v1",
        "attestation_sha256": attestation_id,
        "reason": reason,
        "evidence_sha256s": evidence,
        "predecessor_revocation_sha256": predecessor,
        "revoked": True,
    }
    return MigrationReproductionRevocation(**payload, revocation_sha256=_canonical_sha256(payload))
