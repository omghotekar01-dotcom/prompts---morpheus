from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_e140_e139_comparison_sequence_evidence import (
    E140_DIGEST_FIELD,
    verify_startup_readiness_e140_e139_comparison_sequence,
)


E141_SCHEMA = "morpheus-startup-mvp-readiness-e141-e140-sequence-prefix-comparison-v1"
E141_STATE = "STARTUP_MVP_READINESS_E141_E140_SEQUENCE_PREFIX_COMPARISON_REPLAYABLE_LOCAL_EVIDENCE"


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
        "base_e140_sequence_sha256": base[E140_DIGEST_FIELD],
        "candidate_e140_sequence_sha256": candidate[E140_DIGEST_FIELD],
        "base_comparison_count": len(base_ids),
        "candidate_comparison_count": len(candidate_ids),
        "contains_base_prefix": contains_base_prefix,
        "is_strict_extension": contains_base_prefix and not identical,
        "extension_comparison_count": len(suffix),
        "extension_comparison_sha256s": suffix,
        "relation": relation,
    }


def build_startup_readiness_e141_e140_sequence_prefix_comparison(
    base_sequence: Mapping[str, Any],
    candidate_sequence: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two independently replay-verified E140 sequences for exact ordered comparison-identity prefix structure."""

    base = verify_startup_readiness_e140_e139_comparison_sequence(base_sequence)
    candidate = verify_startup_readiness_e140_e139_comparison_sequence(candidate_sequence)
    core = {
        "schema": E141_SCHEMA,
        "evidence_state": E141_STATE,
        **_comparison_semantics(base, candidate),
        "base_e140_sequence": base,
        "candidate_e140_sequence": candidate,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This record compares two caller-supplied, independently replay-verified local E140 sequences for exact ordered comparison-identity prefix structure only.",
            "A strict prefix relation is not trusted append-only history, chronology, wall-clock freshness, rollback detection/prevention, provenance, authenticity or causality.",
            "A non-prefix result does not identify which supplied sequence is newer, correct, complete, authoritative or maliciously modified.",
            "Suffix identities and counts summarize supplied structural evidence only; they are not benchmark evidence, production-reliability evidence, scientific-superiority evidence, novelty evidence or patentability evidence.",
            "This comparison cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "comparison_sha256": _canonical_sha256(core)}


def verify_startup_readiness_e141_e140_sequence_prefix_comparison(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless nested E140 sequences and all derived E141 prefix semantics replay exactly."""

    payload = deepcopy(dict(record))
    if payload.get("schema") != E141_SCHEMA:
        raise ValueError("unsupported startup readiness E141 E140-sequence prefix-comparison schema")
    if payload.get("evidence_state") != E141_STATE:
        raise ValueError("unexpected startup readiness E141 E140-sequence prefix-comparison state")

    base_sequence = payload.get("base_e140_sequence")
    candidate_sequence = payload.get("candidate_e140_sequence")
    if not isinstance(base_sequence, Mapping) or not isinstance(candidate_sequence, Mapping):
        raise ValueError("startup readiness E141 prefix comparison requires two embedded E140 sequences")
    base = verify_startup_readiness_e140_e139_comparison_sequence(base_sequence)
    candidate = verify_startup_readiness_e140_e139_comparison_sequence(candidate_sequence)

    expected = _comparison_semantics(base, candidate)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness E141 prefix comparison {field} is inconsistent with embedded E140 sequences")

    if not _is_sha256(payload.get("base_e140_sequence_sha256")) or not _is_sha256(payload.get("candidate_e140_sequence_sha256")):
        raise ValueError("startup readiness E141 prefix comparison contains malformed E140 sequence identities")
    suffix_ids = payload.get("extension_comparison_sha256s")
    if not isinstance(suffix_ids, list) or not all(_is_sha256(value) for value in suffix_ids):
        raise ValueError("startup readiness E141 prefix comparison contains malformed suffix identities")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")
    ):
        raise ValueError("startup readiness E141 prefix comparison cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness E141 prefix comparison truth boundaries are missing")

    comparison_sha256 = payload.get("comparison_sha256")
    if not _is_sha256(comparison_sha256):
        raise ValueError("startup readiness E141 prefix comparison digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "comparison_sha256"}
    if _canonical_sha256(core) != comparison_sha256:
        raise ValueError("startup readiness E141 prefix comparison digest does not match canonical record")
    return payload
