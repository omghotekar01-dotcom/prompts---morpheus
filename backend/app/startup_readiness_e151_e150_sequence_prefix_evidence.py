from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_e150_e149_comparison_sequence_evidence import (
    verify_startup_readiness_e150_e149_comparison_sequence,
)

E151_SCHEMA = "morpheus-startup-mvp-readiness-e151-e150-sequence-prefix-comparison-v1"
E151_STATE = "STARTUP_MVP_READINESS_E151_E150_SEQUENCE_PREFIX_COMPARISON_REPLAYABLE_LOCAL_EVIDENCE"
E151_DIGEST_FIELD = "comparison_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")
_AUTHORITY = {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False}
_BOUNDARIES = [
    "This record compares caller-supplied independently replay-verified local E150 structural sequences only.",
    "Ordered E149 digest-prefix structure is local structural evidence only and does not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
    "STRICT_PREFIX_EXTENSION exposes only the exact structural suffix supplied by the candidate sequence and does not identify which state is newer, correct, complete, authoritative or safe for deployment.",
    "This comparison is not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
    "This evidence cannot authorize production deployment, activation or automatic control.",
]


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _prefix_relation(base_ids: list[str], candidate_ids: list[str]) -> tuple[str, list[str]]:
    if candidate_ids == base_ids:
        return "IDENTICAL", []
    if len(candidate_ids) > len(base_ids) and candidate_ids[: len(base_ids)] == base_ids:
        return "STRICT_PREFIX_EXTENSION", candidate_ids[len(base_ids) :]
    return "NOT_PREFIX_EXTENSION", []


def build_startup_readiness_e151_e150_sequence_prefix_comparison(
    base_sequence: Mapping[str, Any], candidate_sequence: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare exact ordered E149 identities from two independently replay-verified E150 sequences."""
    base = verify_startup_readiness_e150_e149_comparison_sequence(base_sequence)
    candidate = verify_startup_readiness_e150_e149_comparison_sequence(candidate_sequence)
    base_identity = base.get("sequence_sha256")
    candidate_identity = candidate.get("sequence_sha256")
    if not _is_sha256(base_identity) or not _is_sha256(candidate_identity):
        raise ValueError("startup readiness E151 requires valid E150 sequence identities")
    base_ids = list(base.get("comparison_sha256s", []))
    candidate_ids = list(candidate.get("comparison_sha256s", []))
    if not base_ids or not candidate_ids or not all(_is_sha256(value) for value in base_ids + candidate_ids):
        raise ValueError("startup readiness E151 requires exact ordered E149 comparison identities")
    relation, suffix = _prefix_relation(base_ids, candidate_ids)
    core = {
        "schema": E151_SCHEMA,
        "evidence_state": E151_STATE,
        "base_e150_sequence_sha256": base_identity,
        "candidate_e150_sequence_sha256": candidate_identity,
        "relation": relation,
        "extension_comparison_sha256s": suffix,
        "extension_comparison_count": len(suffix),
        "base_sequence": deepcopy(base),
        "candidate_sequence": deepcopy(candidate),
        "authority": deepcopy(_AUTHORITY),
        "truth_boundaries": list(_BOUNDARIES),
    }
    return {**core, E151_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e151_e150_sequence_prefix_comparison(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless both embedded E150 sequences and all E151 prefix semantics replay exactly."""
    payload = deepcopy(dict(record))
    if payload.get("schema") != E151_SCHEMA or payload.get("evidence_state") != E151_STATE:
        raise ValueError("unsupported startup readiness E151 comparison record")
    base_raw = payload.get("base_sequence")
    candidate_raw = payload.get("candidate_sequence")
    if not isinstance(base_raw, Mapping) or not isinstance(candidate_raw, Mapping):
        raise ValueError("startup readiness E151 requires embedded E150 sequences")
    base = verify_startup_readiness_e150_e149_comparison_sequence(base_raw)
    candidate = verify_startup_readiness_e150_e149_comparison_sequence(candidate_raw)
    base_identity = base.get("sequence_sha256")
    candidate_identity = candidate.get("sequence_sha256")
    if not _is_sha256(base_identity) or not _is_sha256(candidate_identity):
        raise ValueError("startup readiness E151 contains malformed E150 sequence identities")
    base_ids = list(base.get("comparison_sha256s", []))
    candidate_ids = list(candidate.get("comparison_sha256s", []))
    if not base_ids or not candidate_ids or not all(_is_sha256(value) for value in base_ids + candidate_ids):
        raise ValueError("startup readiness E151 contains malformed E149 comparison identities")
    relation, suffix = _prefix_relation(base_ids, candidate_ids)
    expected = {
        "base_e150_sequence_sha256": base_identity,
        "candidate_e150_sequence_sha256": candidate_identity,
        "relation": relation,
        "extension_comparison_sha256s": suffix,
        "extension_comparison_count": len(suffix),
        "authority": _AUTHORITY,
        "truth_boundaries": _BOUNDARIES,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"startup readiness E151 comparison {field} is inconsistent with embedded sequences")
    if relation not in _RELATIONS:
        raise ValueError("startup readiness E151 comparison relation is unsupported")
    digest = payload.get(E151_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E151 comparison digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E151_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E151 comparison digest does not match canonical record")
    return payload
