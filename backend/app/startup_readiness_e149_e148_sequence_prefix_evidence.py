from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_e148_e147_comparison_sequence_evidence import (
    verify_startup_readiness_e148_e147_comparison_sequence,
)

E149_SCHEMA = "morpheus-startup-mvp-readiness-e149-e148-sequence-prefix-comparison-v1"
E149_STATE = "STARTUP_MVP_READINESS_E149_E148_SEQUENCE_PREFIX_COMPARISON_REPLAYABLE_LOCAL_EVIDENCE"
E149_DIGEST_FIELD = "comparison_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")


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


def build_startup_readiness_e149_e148_sequence_prefix_comparison(
    base_sequence: Mapping[str, Any], candidate_sequence: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare exact ordered E147 identities from two independently replay-verified E148 sequences."""
    base = verify_startup_readiness_e148_e147_comparison_sequence(base_sequence)
    candidate = verify_startup_readiness_e148_e147_comparison_sequence(candidate_sequence)
    base_identity = base.get("sequence_sha256")
    candidate_identity = candidate.get("sequence_sha256")
    if not _is_sha256(base_identity) or not _is_sha256(candidate_identity):
        raise ValueError("startup readiness E149 requires valid E148 sequence identities")
    base_ids = list(base.get("comparison_sha256s", []))
    candidate_ids = list(candidate.get("comparison_sha256s", []))
    if not base_ids or not candidate_ids or not all(_is_sha256(value) for value in base_ids + candidate_ids):
        raise ValueError("startup readiness E149 requires exact ordered E147 comparison identities")
    relation, suffix = _prefix_relation(base_ids, candidate_ids)
    core = {
        "schema": E149_SCHEMA,
        "evidence_state": E149_STATE,
        "base_e148_sequence_sha256": base_identity,
        "candidate_e148_sequence_sha256": candidate_identity,
        "relation": relation,
        "extension_comparison_sha256s": suffix,
        "extension_comparison_count": len(suffix),
        "base_sequence": deepcopy(base),
        "candidate_sequence": deepcopy(candidate),
        "authority": {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False},
        "truth_boundaries": [
            "This record compares caller-supplied independently replay-verified local E148 structural sequences only.",
            "Ordered E147 digest-prefix structure is local structural evidence only and does not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
            "STRICT_PREFIX_EXTENSION exposes only the exact structural suffix supplied by the candidate sequence and does not identify which state is newer, correct, complete, authoritative or safe for deployment.",
            "This comparison is not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
            "This evidence cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, E149_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e149_e148_sequence_prefix_comparison(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless both embedded E148 sequences and all E149 prefix semantics replay exactly."""
    payload = deepcopy(dict(record))
    if payload.get("schema") != E149_SCHEMA or payload.get("evidence_state") != E149_STATE:
        raise ValueError("unsupported startup readiness E149 comparison record")
    base_raw = payload.get("base_sequence")
    candidate_raw = payload.get("candidate_sequence")
    if not isinstance(base_raw, Mapping) or not isinstance(candidate_raw, Mapping):
        raise ValueError("startup readiness E149 requires embedded E148 sequences")
    base = verify_startup_readiness_e148_e147_comparison_sequence(base_raw)
    candidate = verify_startup_readiness_e148_e147_comparison_sequence(candidate_raw)
    base_identity = base.get("sequence_sha256")
    candidate_identity = candidate.get("sequence_sha256")
    if not _is_sha256(base_identity) or not _is_sha256(candidate_identity):
        raise ValueError("startup readiness E149 contains malformed E148 sequence identities")
    base_ids = list(base.get("comparison_sha256s", []))
    candidate_ids = list(candidate.get("comparison_sha256s", []))
    if not base_ids or not candidate_ids or not all(_is_sha256(value) for value in base_ids + candidate_ids):
        raise ValueError("startup readiness E149 contains malformed E147 comparison identities")
    relation, suffix = _prefix_relation(base_ids, candidate_ids)
    expected = {
        "base_e148_sequence_sha256": base_identity,
        "candidate_e148_sequence_sha256": candidate_identity,
        "relation": relation,
        "extension_comparison_sha256s": suffix,
        "extension_comparison_count": len(suffix),
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"startup readiness E149 comparison {field} is inconsistent with embedded sequences")
    if relation not in _RELATIONS:
        raise ValueError("startup readiness E149 comparison relation is unsupported")
    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(authority.get(field) is not False for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")):
        raise ValueError("startup readiness E149 comparison cannot carry activation authority")
    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness E149 comparison truth boundaries are missing")
    digest = payload.get(E149_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E149 comparison digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E149_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E149 comparison digest does not match canonical record")
    return payload
