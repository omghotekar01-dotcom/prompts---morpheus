from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_path_extension_evidence import verify_startup_readiness_coherence_path_extension


COHERENCE_PATH_EXTENSION_CHAIN_SCHEMA = "morpheus-startup-mvp-readiness-coherence-path-extension-chain-v1"
COHERENCE_PATH_EXTENSION_CHAIN_STATE = "STARTUP_MVP_READINESS_COHERENCE_PATH_EXTENSION_CHAIN_REPLAYABLE_LOCAL_EVIDENCE"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _chain_semantics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    relations = Counter(record["relation"] for record in records)
    return {
        "extension_sha256s": [record["extension_sha256"] for record in records],
        "extension_count": len(records),
        "start_path_sha256": records[0]["base_path_sha256"],
        "end_path_sha256": records[-1]["candidate_path_sha256"],
        "relation_counts": {
            "IDENTICAL": relations.get("IDENTICAL", 0),
            "STRICT_PREFIX_EXTENSION": relations.get("STRICT_PREFIX_EXTENSION", 0),
            "NOT_PREFIX_EXTENSION": relations.get("NOT_PREFIX_EXTENSION", 0),
        },
        "strict_extension_transition_count": sum(
            int(record["extension_transition_count"])
            for record in records
            if record["relation"] == "STRICT_PREFIX_EXTENSION"
        ),
    }


def build_startup_readiness_coherence_path_extension_chain(
    extension_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind a caller-ordered adjacent sequence of verified path-extension records.

    Adjacency is structural only. This function does not establish chronology,
    append-only history, freshness, provenance, authenticity or rollback safety.
    """

    if len(extension_records) < 2:
        raise ValueError("startup readiness coherence path extension chain requires at least two records")
    verified = [verify_startup_readiness_coherence_path_extension(record) for record in extension_records]
    identities = [record["extension_sha256"] for record in verified]
    if len(identities) != len(set(identities)):
        raise ValueError("startup readiness coherence path extension chain contains duplicate extension identities")
    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_path_sha256"] != current["base_path_sha256"]:
            raise ValueError("startup readiness coherence path extension chain adjacency is broken")

    core = {
        "schema": COHERENCE_PATH_EXTENSION_CHAIN_SCHEMA,
        "evidence_state": COHERENCE_PATH_EXTENSION_CHAIN_STATE,
        **_chain_semantics(verified),
        "extensions": verified,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This record binds a caller-ordered sequence of independently replay-verified local path-extension records and checks exact digest adjacency only.",
            "Adjacency continuity is not trusted chronology, append-only history, wall-clock freshness, rollback detection/prevention, provenance, authenticity, causality or completeness.",
            "Relation counts and suffix lengths summarize supplied structural records only and do not establish correctness, recency, authority or malicious modification.",
            "This chain is not benchmark evidence, production-reliability evidence, scientific-superiority evidence, novelty evidence or patentability evidence.",
            "The chain cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "chain_sha256": _canonical_sha256(core)}


def verify_startup_readiness_coherence_path_extension_chain(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless an extension-chain record exactly replays all nested evidence."""

    payload = deepcopy(dict(record))
    if payload.get("schema") != COHERENCE_PATH_EXTENSION_CHAIN_SCHEMA:
        raise ValueError("unsupported startup readiness coherence path extension chain schema")
    if payload.get("evidence_state") != COHERENCE_PATH_EXTENSION_CHAIN_STATE:
        raise ValueError("unexpected startup readiness coherence path extension chain state")

    extensions = payload.get("extensions")
    if not isinstance(extensions, list) or len(extensions) < 2 or not all(isinstance(item, Mapping) for item in extensions):
        raise ValueError("startup readiness coherence path extension chain requires at least two embedded records")
    verified = [verify_startup_readiness_coherence_path_extension(item) for item in extensions]
    identities = [item["extension_sha256"] for item in verified]
    if len(identities) != len(set(identities)):
        raise ValueError("startup readiness coherence path extension chain contains duplicate extension identities")
    for previous, current in zip(verified, verified[1:]):
        if previous["candidate_path_sha256"] != current["base_path_sha256"]:
            raise ValueError("startup readiness coherence path extension chain adjacency is broken")

    expected = _chain_semantics(verified)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness coherence path extension chain {field} is inconsistent with embedded records")
    if not all(_is_sha256(value) for value in payload["extension_sha256s"]):
        raise ValueError("startup readiness coherence path extension chain contains malformed extension identities")
    if not _is_sha256(payload.get("start_path_sha256")) or not _is_sha256(payload.get("end_path_sha256")):
        raise ValueError("startup readiness coherence path extension chain contains malformed path identities")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in ("production_deployment_authorized", "automatic_control_allowed", "activation_allowed")
    ):
        raise ValueError("startup readiness coherence path extension chain cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness coherence path extension chain truth boundaries are missing")

    chain_sha256 = payload.get("chain_sha256")
    if not _is_sha256(chain_sha256):
        raise ValueError("startup readiness coherence path extension chain digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "chain_sha256"}
    if _canonical_sha256(core) != chain_sha256:
        raise ValueError("startup readiness coherence path extension chain digest does not match canonical record")
    return payload
