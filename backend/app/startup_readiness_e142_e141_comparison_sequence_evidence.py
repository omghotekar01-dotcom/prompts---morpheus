from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_e141_e140_sequence_prefix_evidence import (
    verify_startup_readiness_e141_e140_sequence_prefix_comparison,
)

E142_SCHEMA = "morpheus-startup-mvp-readiness-e142-e141-comparison-sequence-v1"
E142_STATE = "STARTUP_MVP_READINESS_E142_E141_COMPARISON_SEQUENCE_REPLAYABLE_LOCAL_EVIDENCE"
E142_DIGEST_FIELD = "sequence_sha256"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _sequence_semantics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {relation: 0 for relation in _RELATIONS}
    suffix_total = 0
    for record in records:
        relation = record["relation"]
        if relation not in counts:
            raise ValueError("startup readiness E142 sequence contains unsupported relation")
        counts[relation] += 1
        if relation == "STRICT_PREFIX_EXTENSION":
            suffix_total += int(record["extension_comparison_count"])
    return {
        "comparison_sha256s": [record["comparison_sha256"] for record in records],
        "comparison_count": len(records),
        "start_e140_sequence_sha256": records[0]["base_e140_sequence_sha256"],
        "end_e140_sequence_sha256": records[-1]["candidate_e140_sequence_sha256"],
        "relation_counts": counts,
        "strict_prefix_suffix_comparison_count": suffix_total,
    }


def _verify_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    verified = [verify_startup_readiness_e141_e140_sequence_prefix_comparison(record) for record in records]
    identities = [record["comparison_sha256"] for record in verified]
    if len(set(identities)) != len(identities):
        raise ValueError("startup readiness E142 sequence rejects duplicate comparison identities")
    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_e140_sequence_sha256"] != current["base_e140_sequence_sha256"]:
            raise ValueError("startup readiness E142 sequence has broken structural adjacency")
    return verified


def build_startup_readiness_e142_e141_comparison_sequence(comparison_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Bind caller-ordered independently replay-verified E141 comparisons into local structural evidence."""
    if len(comparison_records) < 2:
        raise ValueError("startup readiness E142 sequence requires at least two E141 records")
    verified = _verify_records(comparison_records)
    core = {
        "schema": E142_SCHEMA,
        "evidence_state": E142_STATE,
        **_sequence_semantics(verified),
        "comparisons": verified,
        "authority": {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False},
        "truth_boundaries": [
            "This record binds caller-ordered independently replay-verified local E141 structural comparisons only.",
            "Digest adjacency does not establish trusted history, chronology, freshness, rollback protection, provenance, authenticity, causality or completeness.",
            "Relation counts and suffix totals are structural summaries only, not benchmark, production-reliability, scientific-superiority, novelty or patentability evidence.",
            "Structural continuity does not identify which supplied state is newer, correct, complete, authoritative or safe for deployment.",
            "This evidence cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, E142_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e142_e141_comparison_sequence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless nested E141 comparisons and all derived E142 semantics replay exactly."""
    payload = deepcopy(dict(record))
    if payload.get("schema") != E142_SCHEMA or payload.get("evidence_state") != E142_STATE:
        raise ValueError("unsupported startup readiness E142 sequence record")
    comparisons = payload.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) < 2 or not all(isinstance(item, Mapping) for item in comparisons):
        raise ValueError("startup readiness E142 sequence requires at least two embedded E141 records")
    verified = _verify_records(comparisons)
    expected = _sequence_semantics(verified)
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"startup readiness E142 sequence {field} is inconsistent with embedded comparisons")
    if not all(_is_sha256(value) for value in payload.get("comparison_sha256s", [])):
        raise ValueError("startup readiness E142 sequence contains malformed comparison identities")
    if not _is_sha256(payload.get("start_e140_sequence_sha256")) or not _is_sha256(payload.get("end_e140_sequence_sha256")):
        raise ValueError("startup readiness E142 sequence contains malformed endpoint identities")
    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(authority.get(field) is not False for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")):
        raise ValueError("startup readiness E142 sequence cannot carry activation authority")
    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness E142 sequence truth boundaries are missing")
    digest = payload.get(E142_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E142 sequence digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E142_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E142 sequence digest does not match canonical record")
    return payload
