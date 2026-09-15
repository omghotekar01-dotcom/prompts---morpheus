from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_e145_e144_sequence_prefix_evidence import (
    verify_startup_readiness_e145_e144_sequence_prefix_comparison,
)

E146_SCHEMA = "morpheus-startup-mvp-readiness-e146-e145-comparison-sequence-v1"
E146_STATE = "STARTUP_MVP_READINESS_E146_E145_COMPARISON_SEQUENCE_REPLAYABLE_LOCAL_EVIDENCE"
E146_DIGEST_FIELD = "sequence_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(record["relation"] for record in records)
    return {
        "relation_counts": {relation: counts.get(relation, 0) for relation in _RELATIONS},
        "strict_prefix_extension_suffix_total": sum(
            record["extension_comparison_count"] for record in records if record["relation"] == "STRICT_PREFIX_EXTENSION"
        ),
    }


def _verify_order(records: Sequence[Mapping[str, Any]]) -> None:
    for previous, current in zip(records, records[1:]):
        if previous["candidate_e144_sequence_sha256"] != current["base_e144_sequence_sha256"]:
            raise ValueError("startup readiness E146 comparisons break exact candidate-to-base E144 sequence adjacency")


def build_startup_readiness_e146_e145_comparison_sequence(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build caller-ordered replay evidence over independently verified E145 comparisons."""
    if isinstance(comparisons, (str, bytes)) or len(comparisons) < 2:
        raise ValueError("startup readiness E146 sequence requires at least two E145 comparisons")
    verified = [verify_startup_readiness_e145_e144_sequence_prefix_comparison(item) for item in comparisons]
    identities = [record["comparison_sha256"] for record in verified]
    if not all(_is_sha256(value) for value in identities) or len(set(identities)) != len(identities):
        raise ValueError("startup readiness E146 sequence rejects malformed or duplicate E145 comparison identities")
    _verify_order(verified)
    core = {
        "schema": E146_SCHEMA,
        "evidence_state": E146_STATE,
        "comparison_sha256s": identities,
        "comparison_count": len(verified),
        "base_e144_sequence_sha256": verified[0]["base_e144_sequence_sha256"],
        "candidate_e144_sequence_sha256": verified[-1]["candidate_e144_sequence_sha256"],
        **_summary(verified),
        "comparisons": deepcopy(verified),
        "authority": {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False},
        "truth_boundaries": [
            "This record sequences caller-supplied independently replay-verified local E145 structural comparisons only.",
            "Exact candidate-to-base adjacency is structural continuity only and does not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
            "Relation counts and strict-prefix suffix totals are deterministic structural summaries, not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
            "Sequence position does not identify which supplied state is newer, correct, complete, authoritative or safe for deployment.",
            "This evidence cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, E146_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e146_e145_comparison_sequence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless embedded E145 comparisons and all E146 sequence semantics replay exactly."""
    payload = deepcopy(dict(record))
    if payload.get("schema") != E146_SCHEMA or payload.get("evidence_state") != E146_STATE:
        raise ValueError("unsupported startup readiness E146 sequence record")
    raw = payload.get("comparisons")
    if not isinstance(raw, list) or len(raw) < 2 or not all(isinstance(item, Mapping) for item in raw):
        raise ValueError("startup readiness E146 sequence requires embedded E145 comparisons")
    verified = [verify_startup_readiness_e145_e144_sequence_prefix_comparison(item) for item in raw]
    identities = [item["comparison_sha256"] for item in verified]
    if not all(_is_sha256(value) for value in identities) or len(set(identities)) != len(identities):
        raise ValueError("startup readiness E146 sequence contains malformed or duplicate comparison identities")
    _verify_order(verified)
    expected = {
        "comparison_sha256s": identities,
        "comparison_count": len(verified),
        "base_e144_sequence_sha256": verified[0]["base_e144_sequence_sha256"],
        "candidate_e144_sequence_sha256": verified[-1]["candidate_e144_sequence_sha256"],
        **_summary(verified),
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"startup readiness E146 sequence {field} is inconsistent with embedded comparisons")
    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(authority.get(field) is not False for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")):
        raise ValueError("startup readiness E146 sequence cannot carry activation authority")
    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness E146 sequence truth boundaries are missing")
    digest = payload.get(E146_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E146 sequence digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E146_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E146 sequence digest does not match canonical record")
    return payload
