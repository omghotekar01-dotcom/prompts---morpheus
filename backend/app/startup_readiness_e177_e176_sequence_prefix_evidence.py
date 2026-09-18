from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_e176_e175_comparison_sequence_evidence import (
    verify_startup_readiness_e176_e175_comparison_sequence,
)

E177_SCHEMA = "morpheus-startup-mvp-readiness-e177-e176-sequence-prefix-comparison-v1"
E177_STATE = "STARTUP_MVP_READINESS_E177_E176_SEQUENCE_PREFIX_COMPARISON_REPLAYABLE_LOCAL_EVIDENCE"
E177_DIGEST_FIELD = "comparison_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")
_AUTHORITY = {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False}
_BOUNDARIES = [
    "This record compares two independently replay-verified caller-supplied E176 sequences as local structural evidence only.",
    "Prefix relation, suffix disclosure, sequence identities, embedded sequences and digest binding do not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
    "Structural prefix relation does not identify which supplied state is newer, correct, complete, authoritative or safe for deployment.",
    "This comparison is not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
    "This evidence cannot authorize production deployment, activation or automatic control.",
]


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _ordered_e175_ids(sequence: Mapping[str, Any]) -> list[str]:
    ids = sequence.get("comparison_sha256s")
    if not isinstance(ids, list) or len(ids) < 2 or not all(_is_sha256(value) for value in ids):
        raise ValueError("startup readiness E177 requires valid ordered E175 comparison identities")
    if len(set(ids)) != len(ids):
        raise ValueError("startup readiness E177 requires unique ordered E175 comparison identities")
    return ids


def _relation(base_ids: list[str], candidate_ids: list[str]) -> tuple[str, list[str]]:
    if candidate_ids == base_ids:
        return "IDENTICAL", []
    if len(candidate_ids) > len(base_ids) and candidate_ids[: len(base_ids)] == base_ids:
        return "STRICT_PREFIX_EXTENSION", candidate_ids[len(base_ids) :]
    return "NOT_PREFIX_EXTENSION", []


def build_startup_readiness_e177_e176_sequence_prefix_comparison(
    base_sequence: Mapping[str, Any], candidate_sequence: Mapping[str, Any]
) -> dict[str, Any]:
    base = verify_startup_readiness_e176_e175_comparison_sequence(base_sequence)
    candidate = verify_startup_readiness_e176_e175_comparison_sequence(candidate_sequence)
    base_id = base.get("sequence_sha256")
    candidate_id = candidate.get("sequence_sha256")
    if not _is_sha256(base_id) or not _is_sha256(candidate_id):
        raise ValueError("startup readiness E177 requires valid E176 sequence identities")
    base_ids = _ordered_e175_ids(base)
    candidate_ids = _ordered_e175_ids(candidate)
    relation, suffix = _relation(base_ids, candidate_ids)
    core = {
        "schema": E177_SCHEMA,
        "evidence_state": E177_STATE,
        "base_e176_sequence_sha256": base_id,
        "candidate_e176_sequence_sha256": candidate_id,
        "relation": relation,
        "extension_comparison_sha256s": suffix,
        "extension_comparison_count": len(suffix),
        "base_sequence": deepcopy(base),
        "candidate_sequence": deepcopy(candidate),
        "authority": deepcopy(_AUTHORITY),
        "truth_boundaries": list(_BOUNDARIES),
    }
    return {**core, E177_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e177_e176_sequence_prefix_comparison(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(record))
    if payload.get("schema") != E177_SCHEMA or payload.get("evidence_state") != E177_STATE:
        raise ValueError("unsupported startup readiness E177 comparison record")
    base_raw = payload.get("base_sequence")
    candidate_raw = payload.get("candidate_sequence")
    if not isinstance(base_raw, Mapping) or not isinstance(candidate_raw, Mapping):
        raise ValueError("startup readiness E177 requires embedded E176 sequences")
    expected = build_startup_readiness_e177_e176_sequence_prefix_comparison(base_raw, candidate_raw)
    if payload != expected:
        raise ValueError("startup readiness E177 comparison is inconsistent with replayed E176 sequences")
    if payload.get("relation") not in _RELATIONS:
        raise ValueError("startup readiness E177 contains unsupported relation")
    return payload
