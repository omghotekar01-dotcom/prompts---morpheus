from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_e142_e141_comparison_sequence_evidence import (
    verify_startup_readiness_e142_e141_comparison_sequence,
)

E143_SCHEMA = "morpheus-startup-mvp-readiness-e143-e142-sequence-prefix-v1"
E143_STATE = "STARTUP_MVP_READINESS_E143_E142_SEQUENCE_PREFIX_REPLAYABLE_LOCAL_EVIDENCE"
E143_DIGEST_FIELD = "comparison_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _semantics(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    base_ids = list(base["comparison_sha256s"])
    candidate_ids = list(candidate["comparison_sha256s"])
    if candidate_ids == base_ids:
        relation = "IDENTICAL"
        suffix: list[str] = []
    elif len(candidate_ids) > len(base_ids) and candidate_ids[: len(base_ids)] == base_ids:
        relation = "STRICT_PREFIX_EXTENSION"
        suffix = candidate_ids[len(base_ids) :]
    else:
        relation = "NOT_PREFIX_EXTENSION"
        suffix = []
    return {
        "base_e142_sequence_sha256": base["sequence_sha256"],
        "candidate_e142_sequence_sha256": candidate["sequence_sha256"],
        "relation": relation,
        "extension_comparison_sha256s": suffix,
        "extension_comparison_count": len(suffix),
    }


def build_startup_readiness_e143_e142_sequence_prefix_comparison(
    base_sequence: Mapping[str, Any], candidate_sequence: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare replay-verified E142 sequences for exact ordered comparison-identity prefix structure."""
    base = verify_startup_readiness_e142_e141_comparison_sequence(base_sequence)
    candidate = verify_startup_readiness_e142_e141_comparison_sequence(candidate_sequence)
    core = {
        "schema": E143_SCHEMA,
        "evidence_state": E143_STATE,
        **_semantics(base, candidate),
        "base_sequence": base,
        "candidate_sequence": candidate,
        "authority": {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False},
        "truth_boundaries": [
            "This record compares caller-supplied independently replay-verified local E142 structural sequences only.",
            "Ordered digest-prefix structure does not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
            "Prefix relation and suffix size are structural facts only, not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
            "A strict prefix does not identify which supplied state is newer, correct, complete, authoritative or safe for deployment.",
            "This evidence cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, E143_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e143_e142_sequence_prefix_comparison(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless nested E142 sequences and all derived prefix semantics replay exactly."""
    payload = deepcopy(dict(record))
    if payload.get("schema") != E143_SCHEMA or payload.get("evidence_state") != E143_STATE:
        raise ValueError("unsupported startup readiness E143 comparison record")
    base_raw = payload.get("base_sequence")
    candidate_raw = payload.get("candidate_sequence")
    if not isinstance(base_raw, Mapping) or not isinstance(candidate_raw, Mapping):
        raise ValueError("startup readiness E143 comparison requires embedded E142 sequences")
    base = verify_startup_readiness_e142_e141_comparison_sequence(base_raw)
    candidate = verify_startup_readiness_e142_e141_comparison_sequence(candidate_raw)
    expected = _semantics(base, candidate)
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"startup readiness E143 comparison {field} is inconsistent with embedded sequences")
    if payload.get("relation") not in _RELATIONS:
        raise ValueError("startup readiness E143 comparison contains unsupported relation")
    if not _is_sha256(payload.get("base_e142_sequence_sha256")) or not _is_sha256(payload.get("candidate_e142_sequence_sha256")):
        raise ValueError("startup readiness E143 comparison contains malformed sequence identities")
    suffix = payload.get("extension_comparison_sha256s")
    if not isinstance(suffix, list) or not all(_is_sha256(value) for value in suffix):
        raise ValueError("startup readiness E143 comparison contains malformed suffix evidence")
    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(authority.get(field) is not False for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")):
        raise ValueError("startup readiness E143 comparison cannot carry activation authority")
    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness E143 comparison truth boundaries are missing")
    digest = payload.get(E143_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E143 comparison digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E143_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E143 comparison digest does not match canonical record")
    return payload
