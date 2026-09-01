from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain import (
    TransitionEvidence,
    verify_pilot_startup_evidence_checkpoint_transition_chain,
)

_SCHEMA = "morpheus-pilot-startup-evidence-checkpoint-transition-chain-extension-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_TRANSITION_CHAIN_EXTENSION"
_TRUTH_BOUNDARY = (
    "This artifact proves that one supplied, independently verified local transition-continuity "
    "chain is an exact one-transition extension of another supplied, independently verified local "
    "transition-continuity chain. It establishes structural prefix continuity only. It does not "
    "prove wall-clock chronology, operator identity, external append-only publication, digital "
    "signature, trusted timestamp, remote attestation, production authorization, security "
    "certification, performance, novelty, or patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "previous_transition_chain_sha256",
    "next_transition_chain_sha256",
    "appended_transition_sha256",
    "previous_transition_count",
    "next_transition_count",
    "starting_chain_sha256",
    "previous_ending_chain_sha256",
    "next_ending_chain_sha256",
    "production_deployment_authorized",
    "truth_boundary",
    "extension_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _verify_exact_extension(
    previous_chain: Mapping[str, Any],
    previous_evidence: Sequence[TransitionEvidence],
    next_chain: Mapping[str, Any],
    next_evidence: Sequence[TransitionEvidence],
) -> bool:
    if not verify_pilot_startup_evidence_checkpoint_transition_chain(
        previous_chain, previous_evidence
    ):
        return False
    if not verify_pilot_startup_evidence_checkpoint_transition_chain(next_chain, next_evidence):
        return False

    previous_digests = previous_chain.get("transition_sha256_chain")
    next_digests = next_chain.get("transition_sha256_chain")
    if not isinstance(previous_digests, list) or not isinstance(next_digests, list):
        return False
    if len(next_digests) != len(previous_digests) + 1:
        return False
    if next_digests[:-1] != previous_digests:
        return False
    if next_chain.get("starting_chain_sha256") != previous_chain.get("starting_chain_sha256"):
        return False
    if next_chain.get("starting_checkpoint_count") != previous_chain.get(
        "starting_checkpoint_count"
    ):
        return False
    if next_chain.get("ending_checkpoint_count") != previous_chain.get(
        "ending_checkpoint_count"
    ) + 1:
        return False

    appended_transition, appended_previous, appended_next = next_evidence[-1]
    if appended_transition.get("transition_sha256") != next_digests[-1]:
        return False
    if appended_transition.get("previous_chain_sha256") != previous_chain.get(
        "ending_chain_sha256"
    ):
        return False
    if appended_previous.get("chain_sha256") != previous_chain.get("ending_chain_sha256"):
        return False
    if appended_next.get("chain_sha256") != next_chain.get("ending_chain_sha256"):
        return False
    return list(next_evidence[:-1]) == list(previous_evidence)


def build_pilot_startup_evidence_checkpoint_transition_chain_extension(
    previous_chain: Mapping[str, Any],
    previous_evidence: Sequence[TransitionEvidence],
    next_chain: Mapping[str, Any],
    next_evidence: Sequence[TransitionEvidence],
) -> dict[str, Any]:
    """Bind an exact one-transition extension between two verified local continuity chains."""

    if not _verify_exact_extension(previous_chain, previous_evidence, next_chain, next_evidence):
        raise ValueError("transition-chain extension must append exactly one verified transition")

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "previous_transition_chain_sha256": previous_chain["transition_chain_sha256"],
        "next_transition_chain_sha256": next_chain["transition_chain_sha256"],
        "appended_transition_sha256": next_chain["transition_sha256_chain"][-1],
        "previous_transition_count": previous_chain["transition_count"],
        "next_transition_count": next_chain["transition_count"],
        "starting_chain_sha256": previous_chain["starting_chain_sha256"],
        "previous_ending_chain_sha256": previous_chain["ending_chain_sha256"],
        "next_ending_chain_sha256": next_chain["ending_chain_sha256"],
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "extension_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
    artifact: Mapping[str, Any],
    previous_chain: Mapping[str, Any],
    previous_evidence: Sequence[TransitionEvidence],
    next_chain: Mapping[str, Any],
    next_evidence: Sequence[TransitionEvidence],
) -> bool:
    """Independently verify a claimed exact one-transition aggregate-chain extension."""

    try:
        if not isinstance(artifact, Mapping) or set(artifact) != _REQUIRED_KEYS:
            return False
        if artifact.get("schema") != _SCHEMA or artifact.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if artifact.get("production_deployment_authorized") is not False:
            return False
        if artifact.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        for key in (
            "previous_transition_chain_sha256",
            "next_transition_chain_sha256",
            "appended_transition_sha256",
            "starting_chain_sha256",
            "previous_ending_chain_sha256",
            "next_ending_chain_sha256",
            "extension_sha256",
        ):
            if not _is_hex64(artifact.get(key)):
                return False

        previous_count = artifact.get("previous_transition_count")
        next_count = artifact.get("next_transition_count")
        if isinstance(previous_count, bool) or not isinstance(previous_count, int) or previous_count < 1:
            return False
        if isinstance(next_count, bool) or not isinstance(next_count, int):
            return False
        if next_count != previous_count + 1:
            return False

        if not _verify_exact_extension(previous_chain, previous_evidence, next_chain, next_evidence):
            return False
        expected = {
            "previous_transition_chain_sha256": previous_chain["transition_chain_sha256"],
            "next_transition_chain_sha256": next_chain["transition_chain_sha256"],
            "appended_transition_sha256": next_chain["transition_sha256_chain"][-1],
            "previous_transition_count": previous_chain["transition_count"],
            "next_transition_count": next_chain["transition_count"],
            "starting_chain_sha256": previous_chain["starting_chain_sha256"],
            "previous_ending_chain_sha256": previous_chain["ending_chain_sha256"],
            "next_ending_chain_sha256": next_chain["ending_chain_sha256"],
        }
        if any(artifact[key] != value for key, value in expected.items()):
            return False

        unsigned = {key: artifact[key] for key in _REQUIRED_KEYS if key != "extension_sha256"}
        return artifact["extension_sha256"] == _digest_payload(unsigned)
    except (IndexError, KeyError, TypeError, ValueError):
        return False
