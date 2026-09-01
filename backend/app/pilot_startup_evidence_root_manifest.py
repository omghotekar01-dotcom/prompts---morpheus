from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import (
    ExtensionEvidence,
    verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain,
)
from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain_store import (
    PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore,
)

_SCHEMA = "morpheus-pilot-startup-evidence-root-manifest-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_STARTUP_EVIDENCE_ROOT"
_TRUTH_BOUNDARY = (
    "This root manifest gives one deterministic content identity for an independently verified "
    "local startup-evidence extension-continuity chain and can be rebound to its immutable local "
    "evidence stores. It is a portability/audit handoff descriptor only. It does not establish "
    "wall-clock chronology, operator identity, a digital signature, trusted timestamp, externally "
    "append-only publication, remote attestation, production authorization, security certification, "
    "benchmark or performance evidence, novelty, or patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "extension_chain_sha256",
    "extension_count",
    "starting_transition_chain_sha256",
    "ending_transition_chain_sha256",
    "starting_transition_count",
    "ending_transition_count",
    "production_deployment_authorized",
    "truth_boundary",
    "root_manifest_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def build_pilot_startup_evidence_root_manifest(
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, Any]:
    """Build a deterministic handoff root for a verified local startup-evidence graph."""

    if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
        extension_chain, evidence
    ):
        raise ValueError("startup evidence extension-continuity chain failed verification")

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "extension_chain_sha256": extension_chain["extension_chain_sha256"],
        "extension_count": extension_chain["extension_count"],
        "starting_transition_chain_sha256": extension_chain["starting_transition_chain_sha256"],
        "ending_transition_chain_sha256": extension_chain["ending_transition_chain_sha256"],
        "starting_transition_count": extension_chain["starting_transition_count"],
        "ending_transition_count": extension_chain["ending_transition_count"],
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "root_manifest_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_root_manifest(
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> bool:
    """Verify the root descriptor and the supplied extension-continuity evidence."""

    try:
        if not isinstance(manifest, Mapping) or set(manifest) != _REQUIRED_KEYS:
            return False
        if manifest.get("schema") != _SCHEMA or manifest.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if manifest.get("production_deployment_authorized") is not False:
            return False
        if manifest.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
            extension_chain, evidence
        ):
            return False

        for key in (
            "extension_chain_sha256",
            "starting_transition_chain_sha256",
            "ending_transition_chain_sha256",
            "root_manifest_sha256",
        ):
            if not _is_hex64(manifest.get(key)):
                return False

        for key in ("extension_count", "starting_transition_count", "ending_transition_count"):
            value = manifest.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return False

        bindings = (
            "extension_chain_sha256",
            "extension_count",
            "starting_transition_chain_sha256",
            "ending_transition_chain_sha256",
            "starting_transition_count",
            "ending_transition_count",
        )
        if any(manifest[key] != extension_chain[key] for key in bindings):
            return False

        unsigned = {
            key: manifest[key] for key in _REQUIRED_KEYS if key != "root_manifest_sha256"
        }
        return manifest["root_manifest_sha256"] == _digest_payload(unsigned)
    except (KeyError, TypeError, ValueError):
        return False


def verify_pilot_startup_evidence_root_manifest_against_stores(
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
    extension_chain_root: str | Path,
    extension_root: str | Path,
    transition_chain_root: str | Path,
    transition_root: str | Path,
    checkpoint_chain_root: str | Path,
) -> bool:
    """Rebind the root manifest through every immutable local startup-evidence store."""

    try:
        if not verify_pilot_startup_evidence_root_manifest(manifest, extension_chain, evidence):
            return False
        digest = manifest.get("extension_chain_sha256")
        if not isinstance(digest, str):
            return False

        store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(
            extension_chain_root
        )
        stored_extension_chain = store.load(digest, evidence)
        if stored_extension_chain != dict(extension_chain):
            return False

        return store.verify_against_evidence_stores(
            digest,
            evidence,
            extension_root,
            transition_chain_root,
            transition_root,
            checkpoint_chain_root,
        )
    except (OSError, ValueError, TypeError):
        return False
