from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence, TypeAlias

from .pilot_startup_evidence_checkpoint_transition_chain import TransitionEvidence
from .pilot_startup_evidence_checkpoint_transition_chain_extension import (
    verify_pilot_startup_evidence_checkpoint_transition_chain_extension,
)

ExtensionEvidence: TypeAlias = tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Sequence[TransitionEvidence],
    Mapping[str, Any],
    Sequence[TransitionEvidence],
]

_SCHEMA = "morpheus-pilot-startup-evidence-checkpoint-transition-chain-extension-chain-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_TRANSITION_CHAIN_EXTENSION_CONTINUITY"
_TRUTH_BOUNDARY = (
    "This artifact proves structural continuity across a supplied sequence of independently "
    "verified local transition-chain extension artifacts. It establishes that each extension's "
    "successor aggregate chain is exactly the next extension's predecessor aggregate chain, with "
    "no replay inside the supplied sequence. It does not prove wall-clock chronology, operator "
    "identity, external append-only publication, digital signature, trusted timestamp, remote "
    "attestation, production authorization, security certification, performance, novelty, or "
    "patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "extension_sha256_chain",
    "extension_count",
    "starting_transition_chain_sha256",
    "ending_transition_chain_sha256",
    "starting_transition_count",
    "ending_transition_count",
    "production_deployment_authorized",
    "truth_boundary",
    "extension_chain_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _verified_extension_sequence(
    evidence: Sequence[ExtensionEvidence],
) -> tuple[list[str], Mapping[str, Any], Mapping[str, Any]] | None:
    if not evidence:
        return None

    digests: list[str] = []
    first_previous: Mapping[str, Any] | None = None
    prior_next_chain: Mapping[str, Any] | None = None
    prior_next_evidence: Sequence[TransitionEvidence] | None = None

    for item in evidence:
        if not isinstance(item, tuple) or len(item) != 5:
            return None
        artifact, previous_chain, previous_evidence, next_chain, next_evidence = item
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
            artifact,
            previous_chain,
            previous_evidence,
            next_chain,
            next_evidence,
        ):
            return None

        digest = artifact.get("extension_sha256")
        if not _is_hex64(digest) or digest in digests:
            return None
        digests.append(digest)

        if first_previous is None:
            first_previous = previous_chain
        else:
            if prior_next_chain != previous_chain:
                return None
            if list(prior_next_evidence or ()) != list(previous_evidence):
                return None

        prior_next_chain = next_chain
        prior_next_evidence = next_evidence

    if first_previous is None or prior_next_chain is None:
        return None
    return digests, first_previous, prior_next_chain


def build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, Any]:
    """Build deterministic local continuity evidence across verified aggregate-chain extensions."""

    verified = _verified_extension_sequence(evidence)
    if verified is None:
        raise ValueError("extension evidence must form one non-replayed contiguous verified sequence")
    digests, first_previous, final_next = verified

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "extension_sha256_chain": digests,
        "extension_count": len(digests),
        "starting_transition_chain_sha256": first_previous["transition_chain_sha256"],
        "ending_transition_chain_sha256": final_next["transition_chain_sha256"],
        "starting_transition_count": first_previous["transition_count"],
        "ending_transition_count": final_next["transition_count"],
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "extension_chain_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
    artifact: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> bool:
    """Independently verify a deterministic sequence of local extension-continuity artifacts."""

    try:
        if not isinstance(artifact, Mapping) or set(artifact) != _REQUIRED_KEYS:
            return False
        if artifact.get("schema") != _SCHEMA or artifact.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if artifact.get("production_deployment_authorized") is not False:
            return False
        if artifact.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False

        chain = artifact.get("extension_sha256_chain")
        if not isinstance(chain, list) or not chain or not all(_is_hex64(item) for item in chain):
            return False
        if len(set(chain)) != len(chain):
            return False

        extension_count = artifact.get("extension_count")
        starting_count = artifact.get("starting_transition_count")
        ending_count = artifact.get("ending_transition_count")
        for count in (extension_count, starting_count, ending_count):
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                return False
        if extension_count != len(chain) or ending_count != starting_count + extension_count:
            return False

        for key in (
            "starting_transition_chain_sha256",
            "ending_transition_chain_sha256",
            "extension_chain_sha256",
        ):
            if not _is_hex64(artifact.get(key)):
                return False

        verified = _verified_extension_sequence(evidence)
        if verified is None:
            return False
        digests, first_previous, final_next = verified
        if chain != digests:
            return False
        if artifact["starting_transition_chain_sha256"] != first_previous["transition_chain_sha256"]:
            return False
        if artifact["ending_transition_chain_sha256"] != final_next["transition_chain_sha256"]:
            return False
        if artifact["starting_transition_count"] != first_previous["transition_count"]:
            return False
        if artifact["ending_transition_count"] != final_next["transition_count"]:
            return False

        unsigned = {
            key: artifact[key] for key in _REQUIRED_KEYS if key != "extension_chain_sha256"
        }
        return artifact["extension_chain_sha256"] == _digest_payload(unsigned)
    except (IndexError, KeyError, TypeError, ValueError):
        return False
