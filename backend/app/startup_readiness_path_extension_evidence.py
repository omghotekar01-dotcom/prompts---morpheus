from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .startup_readiness_path_evidence import verify_startup_readiness_coherence_path


COHERENCE_PATH_EXTENSION_SCHEMA = "morpheus-startup-mvp-readiness-coherence-path-extension-v1"
COHERENCE_PATH_EXTENSION_STATE = "STARTUP_MVP_READINESS_COHERENCE_PATH_EXTENSION_REPLAYABLE_LOCAL_EVIDENCE"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _extension_semantics(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    base_ids = list(base["transition_sha256s"])
    candidate_ids = list(candidate["transition_sha256s"])
    contains_base_prefix = len(candidate_ids) >= len(base_ids) and candidate_ids[: len(base_ids)] == base_ids
    identical = candidate_ids == base_ids
    suffix = candidate_ids[len(base_ids):] if contains_base_prefix else []
    relation = "IDENTICAL" if identical else "STRICT_PREFIX_EXTENSION" if contains_base_prefix else "NOT_PREFIX_EXTENSION"
    return {
        "base_path_sha256": base["path_sha256"],
        "candidate_path_sha256": candidate["path_sha256"],
        "base_transition_count": len(base_ids),
        "candidate_transition_count": len(candidate_ids),
        "contains_base_prefix": contains_base_prefix,
        "is_strict_extension": contains_base_prefix and not identical,
        "extension_transition_count": len(suffix),
        "extension_transition_sha256s": suffix,
        "relation": relation,
    }


def build_startup_readiness_coherence_path_extension(
    base_path: Mapping[str, Any],
    candidate_path: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two supplied replay-verified paths for exact transition-prefix structure.

    Prefix structure is content-local only. It is not a claim of append-only history,
    trusted chronology, freshness, rollback prevention, provenance or authenticity.
    """

    base = verify_startup_readiness_coherence_path(base_path)
    candidate = verify_startup_readiness_coherence_path(candidate_path)
    semantics = _extension_semantics(base, candidate)
    core = {
        "schema": COHERENCE_PATH_EXTENSION_SCHEMA,
        "evidence_state": COHERENCE_PATH_EXTENSION_STATE,
        **semantics,
        "base_path": base,
        "candidate_path": candidate,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This record compares two caller-supplied, replay-verified local paths for exact transition-identity prefix structure only.",
            "A strict prefix extension is not trusted append-only history, trusted chronology, wall-clock freshness, rollback detection/prevention, provenance, authenticity or causality.",
            "A non-prefix result does not identify which supplied path is newer, correct, complete or authoritative and does not establish malicious modification.",
            "This structural comparison is not benchmark evidence, production-reliability evidence, scientific-superiority evidence, novelty evidence or patentability evidence.",
            "The record cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "extension_sha256": _canonical_sha256(core)}


def verify_startup_readiness_coherence_path_extension(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless a path-extension record exactly replays its nested paths and summary."""

    payload = deepcopy(dict(record))
    if payload.get("schema") != COHERENCE_PATH_EXTENSION_SCHEMA:
        raise ValueError("unsupported startup readiness coherence path extension schema")
    if payload.get("evidence_state") != COHERENCE_PATH_EXTENSION_STATE:
        raise ValueError("unexpected startup readiness coherence path extension state")

    base_path = payload.get("base_path")
    candidate_path = payload.get("candidate_path")
    if not isinstance(base_path, Mapping) or not isinstance(candidate_path, Mapping):
        raise ValueError("startup readiness coherence path extension requires two embedded paths")
    base = verify_startup_readiness_coherence_path(base_path)
    candidate = verify_startup_readiness_coherence_path(candidate_path)

    expected = _extension_semantics(base, candidate)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness coherence path extension {field} is inconsistent with embedded paths")

    if not _is_sha256(payload.get("base_path_sha256")) or not _is_sha256(payload.get("candidate_path_sha256")):
        raise ValueError("startup readiness coherence path extension contains malformed path identities")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        raise ValueError("startup readiness coherence path extension authority boundary is missing")
    if any(
        authority.get(field) is not False
        for field in (
            "production_deployment_authorized",
            "automatic_control_allowed",
            "activation_allowed",
        )
    ):
        raise ValueError("startup readiness coherence path extension cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness coherence path extension truth boundaries are missing")

    extension_sha256 = payload.get("extension_sha256")
    if not _is_sha256(extension_sha256):
        raise ValueError("startup readiness coherence path extension digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "extension_sha256"}
    if _canonical_sha256(core) != extension_sha256:
        raise ValueError("startup readiness coherence path extension digest does not match canonical record")
    return payload
