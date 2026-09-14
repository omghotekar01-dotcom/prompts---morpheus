from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence import (
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension,
)


E140_SCHEMA = "morpheus-startup-mvp-readiness-e140-e139-comparison-sequence-v1"
E140_STATE = "STARTUP_MVP_READINESS_E140_E139_COMPARISON_SEQUENCE_REPLAYABLE_LOCAL_EVIDENCE"
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")
_CHAIN_ID_FIELD = "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
E140_DIGEST_FIELD = "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _sequence_semantics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    relation_counts = {relation: 0 for relation in _RELATIONS}
    strict_prefix_suffix_comparison_count = 0
    for record in records:
        relation = record["relation"]
        if relation not in relation_counts:
            raise ValueError("startup readiness E140 comparison sequence contains unsupported relation")
        relation_counts[relation] += 1
        if relation == "STRICT_PREFIX_EXTENSION":
            strict_prefix_suffix_comparison_count += int(record["extension_comparison_count"])
    return {
        "comparison_sha256s": [record["comparison_sha256"] for record in records],
        "comparison_count": len(records),
        "start_e138_chain_sha256": records[0]["base_" + _CHAIN_ID_FIELD],
        "end_e138_chain_sha256": records[-1]["candidate_" + _CHAIN_ID_FIELD],
        "relation_counts": relation_counts,
        "strict_prefix_suffix_comparison_count": strict_prefix_suffix_comparison_count,
    }


def build_startup_readiness_e140_e139_comparison_sequence(
    comparison_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind caller-ordered, independently replay-verified E139 comparisons into local structural sequence evidence."""

    if len(comparison_records) < 2:
        raise ValueError("startup readiness E140 comparison sequence requires at least two E139 records")

    verified = [
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(record)
        for record in comparison_records
    ]
    identities = [record["comparison_sha256"] for record in verified]
    if len(set(identities)) != len(identities):
        raise ValueError("startup readiness E140 comparison sequence rejects duplicate comparison identities")

    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_" + _CHAIN_ID_FIELD] != current["base_" + _CHAIN_ID_FIELD]:
            raise ValueError("startup readiness E140 comparison sequence has broken structural adjacency")

    core = {
        "schema": E140_SCHEMA,
        "evidence_state": E140_STATE,
        **_sequence_semantics(verified),
        "comparisons": verified,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This record binds a caller-ordered sequence of independently replay-verified local E139 structural comparison records only.",
            "Digest adjacency does not establish trusted append-only history, chronology, wall-clock freshness, rollback detection/prevention, provenance, authenticity or causality.",
            "Relation counts and strict-prefix suffix totals summarize supplied structural evidence only and do not establish completeness, benchmark performance, production reliability, scientific superiority, novelty or patentability.",
            "A structurally continuous sequence does not identify which supplied state is newer, correct, complete, authoritative or safe for deployment.",
            "This evidence cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, E140_DIGEST_FIELD: _canonical_sha256(core)}


def verify_startup_readiness_e140_e139_comparison_sequence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless every nested E139 comparison and every derived E140 sequence semantic replays exactly."""

    payload = deepcopy(dict(record))
    if payload.get("schema") != E140_SCHEMA:
        raise ValueError("unsupported startup readiness E140 comparison sequence schema")
    if payload.get("evidence_state") != E140_STATE:
        raise ValueError("unexpected startup readiness E140 comparison sequence state")

    comparisons = payload.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) < 2 or not all(isinstance(item, Mapping) for item in comparisons):
        raise ValueError("startup readiness E140 comparison sequence requires at least two embedded E139 records")
    verified = [
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(item)
        for item in comparisons
    ]
    identities = [item["comparison_sha256"] for item in verified]
    if len(set(identities)) != len(identities):
        raise ValueError("startup readiness E140 comparison sequence contains duplicate comparison identities")
    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_" + _CHAIN_ID_FIELD] != current["base_" + _CHAIN_ID_FIELD]:
            raise ValueError("startup readiness E140 comparison sequence has broken structural adjacency")

    expected = _sequence_semantics(verified)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness E140 comparison sequence {field} is inconsistent with embedded comparisons")

    if not all(_is_sha256(value) for value in payload.get("comparison_sha256s", [])):
        raise ValueError("startup readiness E140 comparison sequence contains malformed comparison identities")
    if not _is_sha256(payload.get("start_e138_chain_sha256")) or not _is_sha256(payload.get("end_e138_chain_sha256")):
        raise ValueError("startup readiness E140 comparison sequence contains malformed endpoint identities")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")
    ):
        raise ValueError("startup readiness E140 comparison sequence cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness E140 comparison sequence truth boundaries are missing")

    digest = payload.get(E140_DIGEST_FIELD)
    if not _is_sha256(digest):
        raise ValueError("startup readiness E140 comparison sequence digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != E140_DIGEST_FIELD}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness E140 comparison sequence digest does not match canonical record")
    return payload
