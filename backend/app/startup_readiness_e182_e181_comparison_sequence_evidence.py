from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_e181_e180_sequence_prefix_evidence import (
    verify_startup_readiness_e181_e180_sequence_prefix_comparison,
)

E182_SCHEMA = "morpheus-startup-mvp-readiness-e182-e181-comparison-sequence-v1"
E182_STATE = "STARTUP_MVP_READINESS_E182_E181_COMPARISON_SEQUENCE_REPLAYABLE_LOCAL_EVIDENCE"
E182_DIGEST_FIELD = "sequence_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")
_AUTHORITY = {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False}
_BOUNDARIES = [
    "This record binds a caller-ordered sequence of independently replay-verified E181 comparisons as local structural evidence only.",
    "Ordering, adjacency, summaries, suffix totals, endpoints, embedded comparisons and digest binding do not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
    "Structural sequence evidence does not identify any supplied state as newer, correct, complete, authoritative or safe for deployment.",
    "This sequence is not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
    "This evidence cannot authorize production deployment, activation or automatic control.",
]


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def build_startup_readiness_e182_e181_comparison_sequence(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if isinstance(comparisons, (str, bytes)) or len(comparisons) < 2:
        raise ValueError("startup readiness E182 requires at least two E181 comparisons")
    verified = [verify_startup_readiness_e181_e180_sequence_prefix_comparison(value) for value in comparisons]
    comparison_ids = [value.get("comparison_sha256") for value in verified]
    if not all(_is_sha256(value) for value in comparison_ids):
        raise ValueError("startup readiness E182 requires valid E181 comparison identities")
    if len(set(comparison_ids)) != len(comparison_ids):
        raise ValueError("startup readiness E182 requires unique E181 comparison identities")
    for previous, current in zip(verified, verified[1:]):
        if previous.get("candidate_e180_sequence_sha256") != current.get("base_e180_sequence_sha256"):
            raise ValueError("startup readiness E182 requires exact candidate-to-base E180 sequence adjacency")
    relations = [value.get("relation") for value in verified]
    if not all(value in _RELATIONS for value in relations):
        raise ValueError("startup readiness E182 contains unsupported E181 relation")
    suffix_total = 0
    for value in verified:
        suffix = value.get("extension_comparison_sha256s")
        count = value.get("extension_comparison_count")
        if not isinstance(suffix, list) or not all(_is_sha256(item) for item in suffix) or count != len(suffix):
            raise ValueError("startup readiness E182 requires consistent E181 suffix semantics")
        if value.get("relation") != "STRICT_PREFIX_EXTENSION" and suffix:
            raise ValueError("startup readiness E182 permits suffix identities only for strict-prefix extensions")
        suffix_total += len(suffix)
    counts = Counter(relations)
    core = {
        "schema": E182_SCHEMA,
        "evidence_state": E182_STATE,
        "comparison_sha256s": comparison_ids,
        "comparison_count": len(verified),
        "start_e180_sequence_sha256": verified[0]["base_e180_sequence_sha256"],
        "end_e180_sequence_sha256": verified[-1]["candidate_e180_sequence_sha256"],
        "relation_counts": {relation: counts.get(relation, 0) for relation in _RELATIONS},
        "strict_prefix_extension_e179_suffix_total": suffix_total,
        "comparisons": deepcopy(verified),
        "authority": deepcopy(_AUTHORITY),
        "truth_boundaries": list(_BOUNDARIES),
    }
    return {**core, E182_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e182_e181_comparison_sequence(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(record))
    if payload.get("schema") != E182_SCHEMA or payload.get("evidence_state") != E182_STATE:
        raise ValueError("unsupported startup readiness E182 sequence record")
    comparisons = payload.get("comparisons")
    if not isinstance(comparisons, list):
        raise ValueError("startup readiness E182 requires embedded E181 comparisons")
    expected = build_startup_readiness_e182_e181_comparison_sequence(comparisons)
    if payload != expected:
        raise ValueError("startup readiness E182 sequence is inconsistent with replayed E181 comparisons")
    return payload
