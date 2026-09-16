from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_e151_e150_sequence_prefix_evidence import (
    verify_startup_readiness_e151_e150_sequence_prefix_comparison,
)

E152_SCHEMA = "morpheus-startup-mvp-readiness-e152-e151-comparison-sequence-v1"
E152_STATE = "STARTUP_MVP_READINESS_E152_E151_COMPARISON_SEQUENCE_REPLAYABLE_LOCAL_EVIDENCE"
E152_DIGEST_FIELD = "sequence_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")
_AUTHORITY = {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False}
_BOUNDARIES = [
    "This record binds a caller-ordered sequence of independently replay-verified local E151 structural comparisons only.",
    "Sequence ordering, adjacency, relation counts, suffix totals and digest binding do not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
    "Sequence position does not identify which supplied state is newer, correct, complete, authoritative or safe for deployment.",
    "This sequence is not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
    "This evidence cannot authorize production deployment, activation or automatic control.",
]


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _verified(comparisons: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(comparisons, (str, bytes)) or len(comparisons) < 2:
        raise ValueError("startup readiness E152 requires at least two E151 comparisons")
    verified = [verify_startup_readiness_e151_e150_sequence_prefix_comparison(item) for item in comparisons]
    ids = [item.get("comparison_sha256") for item in verified]
    if not all(_is_sha256(value) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("startup readiness E152 requires unique valid E151 comparison identities")
    for previous, current in zip(verified, verified[1:]):
        if previous.get("candidate_e150_sequence_sha256") != current.get("base_e150_sequence_sha256"):
            raise ValueError("startup readiness E152 comparison sequence has broken E150 adjacency")
    return verified


def _summary(verified: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {relation: 0 for relation in _RELATIONS}
    suffix_total = 0
    for item in verified:
        relation = item.get("relation")
        if relation not in counts:
            raise ValueError("startup readiness E152 contains unsupported E151 relation")
        counts[relation] += 1
        suffix = item.get("extension_comparison_count")
        if not isinstance(suffix, int) or isinstance(suffix, bool) or suffix < 0:
            raise ValueError("startup readiness E152 contains invalid strict-prefix suffix count")
        if relation != "STRICT_PREFIX_EXTENSION" and suffix != 0:
            raise ValueError("startup readiness E152 contains inconsistent strict-prefix suffix count")
        suffix_total += suffix
    return {"relation_counts": counts, "strict_prefix_extension_comparison_total": suffix_total}


def build_startup_readiness_e152_e151_comparison_sequence(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    verified = _verified(comparisons)
    summary = _summary(verified)
    core = {
        "schema": E152_SCHEMA,
        "evidence_state": E152_STATE,
        "comparison_sha256s": [item["comparison_sha256"] for item in verified],
        "comparison_count": len(verified),
        "start_e150_sequence_sha256": verified[0]["base_e150_sequence_sha256"],
        "end_e150_sequence_sha256": verified[-1]["candidate_e150_sequence_sha256"],
        **summary,
        "comparisons": deepcopy(verified),
        "authority": deepcopy(_AUTHORITY),
        "truth_boundaries": list(_BOUNDARIES),
    }
    return {**core, E152_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e152_e151_comparison_sequence(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(record))
    if payload.get("schema") != E152_SCHEMA or payload.get("evidence_state") != E152_STATE:
        raise ValueError("unsupported startup readiness E152 sequence record")
    raw = payload.get("comparisons")
    if not isinstance(raw, list):
        raise ValueError("startup readiness E152 requires embedded E151 comparisons")
    verified = _verified(raw)
    summary = _summary(verified)
    expected = {
        "comparison_sha256s": [item["comparison_sha256"] for item in verified],
        "comparison_count": len(verified),
        "start_e150_sequence_sha256": verified[0]["base_e150_sequence_sha256"],
        "end_e150_sequence_sha256": verified[-1]["candidate_e150_sequence_sha256"],
        **summary,
        "authority": _AUTHORITY,
        "truth_boundaries": _BOUNDARIES,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"startup readiness E152 sequence {field} is inconsistent with embedded comparisons")
    digest = payload.get(E152_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E152 sequence digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E152_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E152 sequence digest does not match canonical record")
    return payload
