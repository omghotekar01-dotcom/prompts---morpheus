"""Policy gate for promoting independently reproduced MORPHEUS benchmark evidence.

This module deliberately separates cryptographic/lineage consensus from publication
claims. A consensus artifact is necessary but not sufficient: promotion requires a
minimum number of independent reproductions and an explicit policy version.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


class ConsensusPolicyError(ValueError):
    pass


def _sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ConsensusPolicyError(f"{name} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ConsensusPolicyError(f"{name} must be hexadecimal") from exc
    return value.lower()


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConsensusPolicyError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class ReproductionConsensusRelease:
    consensus_sha256: str
    source_revision: str
    independent_reproductions: int
    required_reproductions: int
    policy_version: str
    publication_claims_authorized: bool
    production_deployment_authorized: bool
    release_sha256: str


def evaluate_consensus_release(
    consensus: Mapping[str, Any], *, required_reproductions: int = 2,
    policy_version: str = "morpheus.reproduction-consensus-policy.v1",
) -> ReproductionConsensusRelease:
    """Turn verified consensus metadata into a narrow publication-evidence release.

    This never authorizes production deployment. It only says whether the supplied
    consensus clears the configured independent-reproduction threshold.
    """
    required = _positive_int(required_reproductions, "required_reproductions")
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise ConsensusPolicyError("policy_version must be non-empty")

    consensus_sha = _digest(consensus.get("consensus_sha256"), "consensus_sha256")
    source_revision = consensus.get("source_revision")
    if not isinstance(source_revision, str) or len(source_revision) != 40:
        raise ConsensusPolicyError("source_revision must be a full 40-character Git revision")
    try:
        int(source_revision, 16)
    except ValueError as exc:
        raise ConsensusPolicyError("source_revision must be hexadecimal") from exc

    count = _positive_int(consensus.get("independent_reproductions"), "independent_reproductions")
    authorized = count >= required
    payload = {
        "schema": "morpheus.reproduction_consensus_release.v1",
        "consensus_sha256": consensus_sha,
        "source_revision": source_revision.lower(),
        "independent_reproductions": count,
        "required_reproductions": required,
        "policy_version": policy_version.strip(),
        "publication_claims_authorized": authorized,
        "production_deployment_authorized": False,
    }
    return ReproductionConsensusRelease(**{k: v for k, v in payload.items() if k != "schema"}, release_sha256=_sha256(payload))
