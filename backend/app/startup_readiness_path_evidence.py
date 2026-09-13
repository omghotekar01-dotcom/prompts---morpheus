from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .startup_readiness_evidence import verify_startup_readiness_coherence_transition


COHERENCE_PATH_SCHEMA = "morpheus-startup-mvp-readiness-coherence-path-v1"
COHERENCE_PATH_STATE = "STARTUP_MVP_READINESS_COHERENCE_PATH_REPLAYABLE_LOCAL_EVIDENCE"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value.lower())


def _path_semantics(transitions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    first = transitions[0]
    last = transitions[-1]
    transition_kinds = [str(transition["transition_kind"]) for transition in transitions]
    state_change_kinds = {"COHERENT_TO_DRIFTED", "DRIFTED_TO_COHERENT"}
    drift_kinds = {"COHERENT_TO_DRIFTED", "UNCHANGED_DRIFT", "CHANGED_DRIFT"}
    return {
        "transition_count": len(transitions),
        "start_coherence_sha256": first["before_coherence_sha256"],
        "end_coherence_sha256": last["after_coherence_sha256"],
        "transition_sha256s": [transition["transition_sha256"] for transition in transitions],
        "transition_kinds": transition_kinds,
        "starts_coherent": bool(first["before"]["matches_current"]),
        "ends_coherent": bool(last["after"]["matches_current"]),
        "contains_declared_drift": any(kind in drift_kinds for kind in transition_kinds)
        or any(not bool(transition["before"]["matches_current"]) for transition in transitions),
        "coherence_state_change_count": sum(kind in state_change_kinds for kind in transition_kinds),
    }


def build_startup_readiness_coherence_path(
    transitions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind a caller-ordered continuous path of verified coherence transitions.

    The sequence order is supplied by the caller. Continuity here means only
    adjacent content identities match. It is not trusted chronology, freshness,
    provenance, rollback detection/prevention or causality.
    """

    if isinstance(transitions, (str, bytes)) or len(transitions) < 2:
        raise ValueError("startup readiness coherence path requires at least two transitions")

    verified = [verify_startup_readiness_coherence_transition(item) for item in transitions]
    identities = [str(item["transition_sha256"]) for item in verified]
    if len(identities) != len(set(identities)):
        raise ValueError("startup readiness coherence path contains duplicate transition identities")

    for previous, current in zip(verified, verified[1:]):
        if previous["after_coherence_sha256"] != current["before_coherence_sha256"]:
            raise ValueError("startup readiness coherence path has broken adjacency continuity")

    semantics = _path_semantics(verified)
    core = {
        "schema": COHERENCE_PATH_SCHEMA,
        "evidence_state": COHERENCE_PATH_STATE,
        **semantics,
        "transitions": verified,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "This path binds a caller-ordered sequence of replay-verified local coherence transitions; caller order is not trusted chronology, time, freshness, provenance or causality.",
            "Adjacency continuity proves only that neighboring transition content identities connect; it does not detect or prevent rollback, omission, reordering outside the supplied path or malicious history selection.",
            "Path summaries describe only the supplied transition semantics and do not establish root cause, production reliability, benchmark performance, scientific superiority, novelty or patentability.",
            "The path cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "path_sha256": _canonical_sha256(core)}


def verify_startup_readiness_coherence_path(path: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless a coherence path exactly replays continuity and summaries."""

    payload = deepcopy(dict(path))
    if payload.get("schema") != COHERENCE_PATH_SCHEMA:
        raise ValueError("unsupported startup readiness coherence path schema")
    if payload.get("evidence_state") != COHERENCE_PATH_STATE:
        raise ValueError("unexpected startup readiness coherence path state")

    transitions = payload.get("transitions")
    if not isinstance(transitions, list) or len(transitions) < 2:
        raise ValueError("startup readiness coherence path requires at least two embedded transitions")
    if not all(isinstance(item, Mapping) for item in transitions):
        raise ValueError("startup readiness coherence path contains malformed transitions")

    verified = [verify_startup_readiness_coherence_transition(item) for item in transitions]
    identities = [str(item["transition_sha256"]) for item in verified]
    if any(not _is_sha256(identity) for identity in identities):
        raise ValueError("startup readiness coherence path contains malformed transition identities")
    if len(identities) != len(set(identities)):
        raise ValueError("startup readiness coherence path contains duplicate transition identities")

    for previous, current in zip(verified, verified[1:]):
        if previous["after_coherence_sha256"] != current["before_coherence_sha256"]:
            raise ValueError("startup readiness coherence path has broken adjacency continuity")

    expected = _path_semantics(verified)
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"startup readiness coherence path {field} is inconsistent with embedded transitions")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        raise ValueError("startup readiness coherence path authority boundary is missing")
    if any(
        authority.get(field) is not False
        for field in (
            "production_deployment_authorized",
            "automatic_control_allowed",
            "activation_allowed",
        )
    ):
        raise ValueError("startup readiness coherence path cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness coherence path truth boundaries are missing")

    path_sha256 = payload.get("path_sha256")
    if not _is_sha256(path_sha256):
        raise ValueError("startup readiness coherence path digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "path_sha256"}
    if _canonical_sha256(core) != path_sha256:
        raise ValueError("startup readiness coherence path digest does not match canonical record")
    return payload
