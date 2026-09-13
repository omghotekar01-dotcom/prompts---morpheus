from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_evidence import (
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain,
)


COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_SCHEMA = (
    "morpheus-startup-mvp-readiness-coherence-path-extension-chain-comparison-chain-extension-chain-extension-chain-extension-v1"
)
COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_STATE = (
    "STARTUP_MVP_READINESS_COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_REPLAYABLE_LOCAL_EVIDENCE"
)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _comparison_semantics(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    base_ids = list(base["comparison_sha256s"])
    candidate_ids = list(candidate["comparison_sha256s"])
    contains_base_prefix = len(candidate_ids) >= len(base_ids) and candidate_ids[: len(base_ids)] == base_ids
    identical = candidate_ids == base_ids
    suffix = candidate_ids[len(base_ids):] if contains_base_prefix else []
    relation = "IDENTICAL" if identical else "STRICT_PREFIX_EXTENSION" if contains_base_prefix else "NOT_PREFIX_EXTENSION"
    return {
        "base_comparison_extension_chain_extension_chain_sha256": base["comparison_extension_chain_extension_chain_sha256"],
        "candidate_comparison_extension_chain_extension_chain_sha256": candidate["comparison_extension_chain_extension_chain_sha256"],
        "base_comparison_count": len(base_ids),
        "candidate_comparison_count": len(candidate_ids),
        "contains_base_prefix": contains_base_prefix,
        "is_strict_extension": contains_base_prefix and not identical,
        "extension_comparison_count": len(suffix),
        "extension_comparison_sha256s": suffix,
        "relation": relation,
    }


def build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(
    base_chain: Mapping[str, Any],
    candidate_chain: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two replay-verified E132 chains for exact ordered identity-prefix structure."""

    base = verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain(base_chain)
    candidate = verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain(candidate_chain)
    core = {
        "schema": COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_SCHEMA,
        "evidence_state": COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_STATE,
        **_comparison_semantics(base, candidate),
        "base_comparison_extension_chain_extension_chain": base,
        "candidate_comparison_extension_chain_extension_chain": candidate,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This record compares two caller-supplied, independently replay-verified local E132 chains for exact ordered comparison-identity prefix structure only.",
            "A strict prefix relation is not trusted append-only history, chronology, wall-clock freshness, rollback detection/prevention, provenance, authenticity or causality.",
            "A non-prefix result does not identify which supplied chain is newer, correct, complete, authoritative or maliciously modified.",
            "Suffix identities and counts summarize supplied structural evidence only; they are not benchmark evidence, production-reliability evidence, scientific-superiority evidence, novelty evidence or patentability evidence.",
            "This comparison cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "comparison_sha256": _canonical_sha256(core)}


def verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless nested E132 chains and all derived prefix semantics replay exactly."""

    payload = deepcopy(dict(record))
    if payload.get("schema") != COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_SCHEMA:
        raise ValueError("unsupported startup readiness comparison-prefix extension-chain comparison schema")
    if payload.get("evidence_state") != COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_EXTENSION_CHAIN_EXTENSION_STATE:
        raise ValueError("unexpected startup readiness comparison-prefix extension-chain comparison state")

    base_chain = payload.get("base_comparison_extension_chain_extension_chain")
    candidate_chain = payload.get("candidate_comparison_extension_chain_extension_chain")
    if not isinstance(base_chain, Mapping) or not isinstance(candidate_chain, Mapping):
        raise ValueError("startup readiness comparison-prefix extension-chain comparison requires two embedded chains")
    base = verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain(base_chain)
    candidate = verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain(candidate_chain)

    expected = _comparison_semantics(base, candidate)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness comparison-prefix extension-chain comparison {field} is inconsistent with embedded chains")

    if not _is_sha256(payload.get("base_comparison_extension_chain_extension_chain_sha256")) or not _is_sha256(
        payload.get("candidate_comparison_extension_chain_extension_chain_sha256")
    ):
        raise ValueError("startup readiness comparison-prefix extension-chain comparison contains malformed chain identities")
    suffix_ids = payload.get("extension_comparison_sha256s")
    if not isinstance(suffix_ids, list) or not all(_is_sha256(value) for value in suffix_ids):
        raise ValueError("startup readiness comparison-prefix extension-chain comparison contains malformed suffix identities")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")
    ):
        raise ValueError("startup readiness comparison-prefix extension-chain comparison cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness comparison-prefix extension-chain comparison truth boundaries are missing")

    comparison_sha256 = payload.get("comparison_sha256")
    if not _is_sha256(comparison_sha256):
        raise ValueError("startup readiness comparison-prefix extension-chain comparison digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "comparison_sha256"}
    if _canonical_sha256(core) != comparison_sha256:
        raise ValueError("startup readiness comparison-prefix extension-chain comparison digest does not match canonical record")
    return payload
