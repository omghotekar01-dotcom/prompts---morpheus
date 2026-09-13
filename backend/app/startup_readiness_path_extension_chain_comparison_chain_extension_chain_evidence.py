from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_path_extension_chain_comparison_chain_extension_evidence import (
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension,
)


COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_SCHEMA = (
    "morpheus-startup-mvp-readiness-coherence-path-extension-chain-comparison-chain-extension-chain-v1"
)
COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_STATE = (
    "STARTUP_MVP_READINESS_COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_REPLAYABLE_LOCAL_EVIDENCE"
)
_RELATIONS = ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _chain_semantics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    relation_counts = {relation: 0 for relation in _RELATIONS}
    strict_prefix_suffix_comparison_count = 0
    for record in records:
        relation = record["relation"]
        relation_counts[relation] += 1
        if relation == "STRICT_PREFIX_EXTENSION":
            strict_prefix_suffix_comparison_count += int(record["extension_comparison_count"])
    return {
        "comparison_sha256s": [record["comparison_sha256"] for record in records],
        "comparison_count": len(records),
        "start_comparison_chain_sha256": records[0]["base_comparison_chain_sha256"],
        "end_comparison_chain_sha256": records[-1]["candidate_comparison_chain_sha256"],
        "relation_counts": relation_counts,
        "strict_prefix_suffix_comparison_count": strict_prefix_suffix_comparison_count,
    }


def build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain(
    comparison_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind caller-ordered, replay-verified comparison-chain prefix records into local evidence.

    Structural adjacency is not trusted chronology, provenance, freshness, rollback
    protection, causality, benchmark evidence or production authority.
    """

    if len(comparison_records) < 2:
        raise ValueError("startup readiness comparison-extension chain requires at least two comparison records")

    verified = [
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(record)
        for record in comparison_records
    ]
    identities = [record["comparison_sha256"] for record in verified]
    if len(set(identities)) != len(identities):
        raise ValueError("startup readiness comparison-extension chain rejects duplicate comparison identities")

    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_comparison_chain_sha256"] != current["base_comparison_chain_sha256"]:
            raise ValueError("startup readiness comparison-extension chain has broken structural adjacency")

    core = {
        "schema": COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_SCHEMA,
        "evidence_state": COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_STATE,
        **_chain_semantics(verified),
        "comparisons": verified,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This record binds a caller-ordered sequence of independently replay-verified local comparison-chain prefix records only.",
            "Digest adjacency does not establish trusted append-only history, chronology, wall-clock freshness, rollback detection/prevention, provenance, authenticity or causality.",
            "Relation counts and strict-prefix suffix totals summarize supplied structural evidence only and do not establish completeness, benchmark performance, production reliability, scientific superiority, novelty or patentability.",
            "A structurally continuous sequence does not identify which supplied state is newer, correct, authoritative or safe for deployment.",
            "This evidence cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "comparison_extension_chain_sha256": _canonical_sha256(core)}


def verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless every nested comparison and all derived chain semantics replay exactly."""

    payload = deepcopy(dict(record))
    if payload.get("schema") != COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_SCHEMA:
        raise ValueError("unsupported startup readiness comparison-extension chain schema")
    if payload.get("evidence_state") != COHERENCE_PATH_EXTENSION_CHAIN_COMPARISON_CHAIN_EXTENSION_CHAIN_STATE:
        raise ValueError("unexpected startup readiness comparison-extension chain state")

    comparisons = payload.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) < 2 or not all(isinstance(item, Mapping) for item in comparisons):
        raise ValueError("startup readiness comparison-extension chain requires at least two embedded comparisons")
    verified = [
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(item)
        for item in comparisons
    ]
    identities = [item["comparison_sha256"] for item in verified]
    if len(set(identities)) != len(identities):
        raise ValueError("startup readiness comparison-extension chain contains duplicate comparison identities")
    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_comparison_chain_sha256"] != current["base_comparison_chain_sha256"]:
            raise ValueError("startup readiness comparison-extension chain has broken structural adjacency")

    expected = _chain_semantics(verified)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness comparison-extension chain {field} is inconsistent with embedded comparisons")

    if not all(_is_sha256(value) for value in payload.get("comparison_sha256s", [])):
        raise ValueError("startup readiness comparison-extension chain contains malformed comparison identities")
    if not _is_sha256(payload.get("start_comparison_chain_sha256")) or not _is_sha256(
        payload.get("end_comparison_chain_sha256")
    ):
        raise ValueError("startup readiness comparison-extension chain contains malformed endpoint identities")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")
    ):
        raise ValueError("startup readiness comparison-extension chain cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness comparison-extension chain truth boundaries are missing")

    digest = payload.get("comparison_extension_chain_sha256")
    if not _is_sha256(digest):
        raise ValueError("startup readiness comparison-extension chain digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "comparison_extension_chain_sha256"}
    if _canonical_sha256(core) != digest:
        raise ValueError("startup readiness comparison-extension chain digest does not match canonical record")
    return payload
