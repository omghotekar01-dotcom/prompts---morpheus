from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition import (
    verify_pilot_startup_evidence_checkpoint_transition,
)

_SCHEMA = "morpheus-pilot-startup-evidence-checkpoint-transition-chain-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_TRANSITION_CONTINUITY"
_TRUTH_BOUNDARY = (
    "This artifact binds an explicit local sequence of independently verified one-checkpoint "
    "transition receipts and proves structural contiguity of that supplied sequence only. It does "
    "not prove wall-clock chronology, operator identity, external append-only publication, digital "
    "signature, trusted timestamp, remote attestation, production authorization, security "
    "certification, performance, novelty, or patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "transition_count",
    "transition_sha256_chain",
    "starting_chain_sha256",
    "ending_chain_sha256",
    "starting_checkpoint_count",
    "ending_checkpoint_count",
    "production_deployment_authorized",
    "truth_boundary",
    "transition_chain_sha256",
}

TransitionEvidence = tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _verified_sequence(evidence: Iterable[TransitionEvidence]) -> list[TransitionEvidence]:
    items = list(evidence)
    if not items:
        raise ValueError("transition chain must contain at least one verified transition")

    seen_transitions: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, tuple) or len(item) != 3:
            raise ValueError("each transition entry must contain receipt, previous chain, and next chain")
        transition, previous_chain, next_chain = item
        if not verify_pilot_startup_evidence_checkpoint_transition(
            transition, previous_chain, next_chain
        ):
            raise ValueError("transition chain contains an unverified transition")
        digest = transition["transition_sha256"]
        if digest in seen_transitions:
            raise ValueError("transition chain cannot replay a transition receipt")
        seen_transitions.add(digest)

        if index > 0:
            prior_transition, _prior_previous, prior_next = items[index - 1]
            if prior_transition["next_chain_sha256"] != transition["previous_chain_sha256"]:
                raise ValueError("transition chain must be structurally contiguous")
            if prior_next["chain_sha256"] != previous_chain["chain_sha256"]:
                raise ValueError("transition chain contains inconsistent shared chain evidence")
    return items


def build_pilot_startup_evidence_checkpoint_transition_chain(
    evidence: Iterable[TransitionEvidence],
) -> dict[str, Any]:
    """Bind a contiguous local path of independently verified one-checkpoint transitions."""

    items = _verified_sequence(evidence)
    first_transition, first_previous, _first_next = items[0]
    last_transition, _last_previous, last_next = items[-1]
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "transition_count": len(items),
        "transition_sha256_chain": [item[0]["transition_sha256"] for item in items],
        "starting_chain_sha256": first_transition["previous_chain_sha256"],
        "ending_chain_sha256": last_transition["next_chain_sha256"],
        "starting_checkpoint_count": first_previous["checkpoint_count"],
        "ending_checkpoint_count": last_next["checkpoint_count"],
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "transition_chain_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_checkpoint_transition_chain(
    artifact: Mapping[str, Any],
    evidence: Sequence[TransitionEvidence],
) -> bool:
    """Independently verify path integrity against every full transition and chain artifact."""

    try:
        if not isinstance(artifact, Mapping) or set(artifact) != _REQUIRED_KEYS:
            return False
        if artifact.get("schema") != _SCHEMA or artifact.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if artifact.get("production_deployment_authorized") is not False:
            return False
        if artifact.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False

        count = artifact.get("transition_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            return False
        digests = artifact.get("transition_sha256_chain")
        if not isinstance(digests, list) or len(digests) != count:
            return False
        if any(not _is_hex64(value) for value in digests) or len(set(digests)) != len(digests):
            return False
        for key in ("starting_chain_sha256", "ending_chain_sha256", "transition_chain_sha256"):
            if not _is_hex64(artifact.get(key)):
                return False

        start_count = artifact.get("starting_checkpoint_count")
        end_count = artifact.get("ending_checkpoint_count")
        if isinstance(start_count, bool) or not isinstance(start_count, int) or start_count < 1:
            return False
        if isinstance(end_count, bool) or not isinstance(end_count, int):
            return False
        if end_count != start_count + count:
            return False

        items = _verified_sequence(evidence)
        if len(items) != count:
            return False
        expected_digests = [item[0]["transition_sha256"] for item in items]
        if digests != expected_digests:
            return False
        if artifact["starting_chain_sha256"] != items[0][0]["previous_chain_sha256"]:
            return False
        if artifact["ending_chain_sha256"] != items[-1][0]["next_chain_sha256"]:
            return False
        if start_count != items[0][1]["checkpoint_count"]:
            return False
        if end_count != items[-1][2]["checkpoint_count"]:
            return False

        unsigned = {key: artifact[key] for key in _REQUIRED_KEYS if key != "transition_chain_sha256"}
        return artifact["transition_chain_sha256"] == _digest_payload(unsigned)
    except (KeyError, TypeError, ValueError):
        return False
