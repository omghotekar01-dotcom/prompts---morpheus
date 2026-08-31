"""Deterministic evidence-chain construction and independent verification.

This module provides a small fail-closed primitive for binding ordered verification
artifacts without granting deployment authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

SCHEMA = "morpheus.evidence_chain.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED = {
    "schema",
    "source_revision",
    "evidence_digests",
    "evidence_count",
    "chain_digest",
    "production_deployment_authorized",
}


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def build_evidence_chain(source_revision: str, evidence_digests: Iterable[str]) -> dict[str, Any]:
    digests = list(evidence_digests)
    if not source_revision or not re.fullmatch(r"[0-9a-f]{7,64}", source_revision):
        raise ValueError("source_revision must be lowercase hexadecimal")
    if not digests or any(not isinstance(x, str) or not _SHA256.fullmatch(x) for x in digests):
        raise ValueError("evidence digests must be non-empty canonical SHA-256 values")
    if len(set(digests)) != len(digests):
        raise ValueError("duplicate evidence digest")
    ordered = sorted(digests)
    core = {
        "schema": SCHEMA,
        "source_revision": source_revision,
        "evidence_digests": ordered,
        "evidence_count": len(ordered),
        "production_deployment_authorized": False,
    }
    return {**core, "chain_digest": hashlib.sha256(_canonical(core)).hexdigest()}


def verify_evidence_chain(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or set(payload) != _ALLOWED:
        return False
    if payload.get("schema") != SCHEMA or payload.get("production_deployment_authorized") is not False:
        return False
    revision = payload.get("source_revision")
    digests = payload.get("evidence_digests")
    count = payload.get("evidence_count")
    digest = payload.get("chain_digest")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{7,64}", revision):
        return False
    if not isinstance(digests, list) or not digests or digests != sorted(digests):
        return False
    if any(not isinstance(x, str) or not _SHA256.fullmatch(x) for x in digests) or len(set(digests)) != len(digests):
        return False
    if type(count) is not int or count != len(digests):
        return False
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return False
    core = {k: payload[k] for k in _ALLOWED if k != "chain_digest"}
    return hashlib.sha256(_canonical(core)).hexdigest() == digest
