from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore

_SCHEMA = "morpheus-pilot-startup-evidence-checkpoint-chain-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_AUDIT_CHAIN"
_TRUTH_BOUNDARY = (
    "This chain records an explicit local ordering of independently verified startup-evidence "
    "catalog checkpoints for audit and reproduction. It is not a digital signature, trusted "
    "timestamp, append-only external log, remote attestation, production authorization, security "
    "certification, performance proof, novelty claim, or patent evidence."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "checkpoint_count",
    "catalog_sha256_chain",
    "production_deployment_authorized",
    "truth_boundary",
    "chain_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalize_digests(catalog_sha256_chain: Iterable[str]) -> list[str]:
    digests = list(catalog_sha256_chain)
    if not digests:
        raise ValueError("checkpoint chain must contain at least one catalog digest")
    for digest in digests:
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            raise ValueError("catalog digests must be 64 lowercase hexadecimal characters")
    if len(set(digests)) != len(digests):
        raise ValueError("checkpoint chain cannot replay a catalog digest")
    return digests


def build_pilot_startup_evidence_checkpoint_chain(
    catalog_sha256_chain: Iterable[str],
) -> dict[str, Any]:
    """Build a deterministic local ordering over verified catalog checkpoint identities.

    Ordering is explicit input and therefore evidence about local operator intent only. This
    function does not infer chronology and deliberately contains no wall-clock timestamp.
    """

    digests = _normalize_digests(catalog_sha256_chain)
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "checkpoint_count": len(digests),
        "catalog_sha256_chain": digests,
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "chain_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_checkpoint_chain(chain: Mapping[str, Any]) -> bool:
    try:
        if not isinstance(chain, Mapping) or set(chain) != _REQUIRED_KEYS:
            return False
        if chain.get("schema") != _SCHEMA or chain.get("evidence_state") != _EVIDENCE_STATE:
            return False
        count = chain.get("checkpoint_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            return False
        digests = chain.get("catalog_sha256_chain")
        if not isinstance(digests, list) or len(digests) != count:
            return False
        if any(not isinstance(value, str) or _HEX64.fullmatch(value) is None for value in digests):
            return False
        if len(set(digests)) != len(digests):
            return False
        if chain.get("production_deployment_authorized") is not False:
            return False
        if chain.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        digest = chain.get("chain_sha256")
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            return False
        unsigned = {key: chain[key] for key in _REQUIRED_KEYS if key != "chain_sha256"}
        return digest == _digest_payload(unsigned)
    except (KeyError, TypeError, ValueError):
        return False


def verify_pilot_startup_evidence_checkpoint_chain_against_store(
    chain: Mapping[str, Any], checkpoint_root: str | Path
) -> bool:
    """Require every catalog identity in a verified chain to exist and verify in the store."""

    if not verify_pilot_startup_evidence_checkpoint_chain(chain):
        return False
    store = PilotStartupEvidenceCatalogStore(checkpoint_root)
    try:
        for catalog_sha256 in chain["catalog_sha256_chain"]:
            store.load(catalog_sha256)
    except (OSError, ValueError):
        return False
    return True
