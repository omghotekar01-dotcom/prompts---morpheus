from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .pilot_startup_evidence_checkpoint_chain import (
    verify_pilot_startup_evidence_checkpoint_chain,
)

_SCHEMA = "morpheus-pilot-startup-evidence-checkpoint-transition-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_CHAIN_EXTENSION"
_TRUTH_BOUNDARY = (
    "This receipt proves only that two independently verified local checkpoint chains are related "
    "by an exact one-catalog append operation. It does not prove wall-clock chronology, operator "
    "identity, external append-only publication, digital signature, trusted timestamp, remote "
    "attestation, production authorization, security certification, performance, novelty, or "
    "patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "previous_chain_sha256",
    "next_chain_sha256",
    "appended_catalog_sha256",
    "previous_checkpoint_count",
    "next_checkpoint_count",
    "production_deployment_authorized",
    "truth_boundary",
    "transition_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _is_exact_one_checkpoint_extension(
    previous_chain: Mapping[str, Any], next_chain: Mapping[str, Any]
) -> bool:
    if not verify_pilot_startup_evidence_checkpoint_chain(previous_chain):
        return False
    if not verify_pilot_startup_evidence_checkpoint_chain(next_chain):
        return False

    previous_digests = previous_chain["catalog_sha256_chain"]
    next_digests = next_chain["catalog_sha256_chain"]
    if len(next_digests) != len(previous_digests) + 1:
        return False
    return next_digests[:-1] == previous_digests


def build_pilot_startup_evidence_checkpoint_transition(
    previous_chain: Mapping[str, Any], next_chain: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind a strict one-checkpoint extension between two verified local chains.

    The relationship is structural, not temporal: no timestamp or external ordering authority is
    inferred. Both chains must already pass their independent integrity verification.
    """

    if not _is_exact_one_checkpoint_extension(previous_chain, next_chain):
        raise ValueError("next checkpoint chain must be an exact one-catalog extension of previous chain")

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "previous_chain_sha256": previous_chain["chain_sha256"],
        "next_chain_sha256": next_chain["chain_sha256"],
        "appended_catalog_sha256": next_chain["catalog_sha256_chain"][-1],
        "previous_checkpoint_count": previous_chain["checkpoint_count"],
        "next_checkpoint_count": next_chain["checkpoint_count"],
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "transition_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_checkpoint_transition(
    transition: Mapping[str, Any],
    previous_chain: Mapping[str, Any],
    next_chain: Mapping[str, Any],
) -> bool:
    """Independently verify a transition receipt against both full checkpoint chains."""

    try:
        if not isinstance(transition, Mapping) or set(transition) != _REQUIRED_KEYS:
            return False
        if transition.get("schema") != _SCHEMA or transition.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if transition.get("production_deployment_authorized") is not False:
            return False
        if transition.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False

        for key in (
            "previous_chain_sha256",
            "next_chain_sha256",
            "appended_catalog_sha256",
            "transition_sha256",
        ):
            if not _is_hex64(transition.get(key)):
                return False

        previous_count = transition.get("previous_checkpoint_count")
        next_count = transition.get("next_checkpoint_count")
        if isinstance(previous_count, bool) or not isinstance(previous_count, int) or previous_count < 1:
            return False
        if isinstance(next_count, bool) or not isinstance(next_count, int) or next_count != previous_count + 1:
            return False

        if not _is_exact_one_checkpoint_extension(previous_chain, next_chain):
            return False
        if transition["previous_chain_sha256"] != previous_chain["chain_sha256"]:
            return False
        if transition["next_chain_sha256"] != next_chain["chain_sha256"]:
            return False
        if transition["appended_catalog_sha256"] != next_chain["catalog_sha256_chain"][-1]:
            return False
        if previous_count != previous_chain["checkpoint_count"]:
            return False
        if next_count != next_chain["checkpoint_count"]:
            return False

        unsigned = {key: transition[key] for key in _REQUIRED_KEYS if key != "transition_sha256"}
        return transition["transition_sha256"] == _digest_payload(unsigned)
    except (KeyError, TypeError, ValueError):
        return False
