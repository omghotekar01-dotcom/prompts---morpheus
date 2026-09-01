from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_handoff_replay_receipt_store import (
    load_pilot_startup_evidence_handoff_replay_receipt,
)

_SCHEMA = "morpheus-pilot-startup-evidence-handoff-replay-descriptor-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_TRANSPORTED_REPLAY_DESCRIPTOR"
_TRUTH_BOUNDARY = (
    "This descriptor content-binds one persisted MORPHEUS transported semantic-replay receipt to the "
    "portable handoff, complete-bundle, and root-manifest identities that the receipt freshly verifies. "
    "It is a deterministic local audit descriptor only. It is not a digital signature, trusted timestamp, "
    "signer/operator identity, external attestation, externally append-only publication, production "
    "deployment authorization, security certification, benchmark/performance evidence, novelty evidence, "
    "or patentability evidence."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "replay_receipt_sha256",
    "handoff_manifest_sha256",
    "complete_bundle_manifest_sha256",
    "root_manifest_sha256",
    "semantic_replay_required",
    "production_deployment_authorized",
    "truth_boundary",
    "replay_descriptor_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def build_pilot_startup_evidence_handoff_replay_descriptor(
    receipt_path: str | Path,
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, Any]:
    """Build a descriptor only after the persisted receipt passes fresh semantic replay.

    The descriptor improves local evidence discoverability and identity continuity. It deliberately does
    not convert local verification into external trust, chronology, deployment authority, scientific
    performance evidence, novelty evidence, or patent evidence.
    """

    receipt = load_pilot_startup_evidence_handoff_replay_receipt(
        receipt_path, bundle_dir, manifest, extension_chain, evidence
    )
    for key in (
        "replay_receipt_sha256",
        "handoff_manifest_sha256",
        "complete_bundle_manifest_sha256",
        "root_manifest_sha256",
    ):
        if not _is_hex64(receipt.get(key)):
            raise ValueError(f"verified replay receipt has invalid {key}")

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "replay_receipt_sha256": receipt["replay_receipt_sha256"],
        "handoff_manifest_sha256": receipt["handoff_manifest_sha256"],
        "complete_bundle_manifest_sha256": receipt["complete_bundle_manifest_sha256"],
        "root_manifest_sha256": receipt["root_manifest_sha256"],
        "semantic_replay_required": True,
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "replay_descriptor_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_handoff_replay_descriptor(
    descriptor: Mapping[str, Any],
    receipt_path: str | Path,
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> bool:
    """Fail closed unless the descriptor matches a freshly re-verified persisted replay receipt."""

    try:
        if not isinstance(descriptor, Mapping) or set(descriptor) != _REQUIRED_KEYS:
            return False
        if descriptor.get("schema") != _SCHEMA or descriptor.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if descriptor.get("semantic_replay_required") is not True:
            return False
        if descriptor.get("production_deployment_authorized") is not False:
            return False
        if descriptor.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        for key in (
            "replay_receipt_sha256",
            "handoff_manifest_sha256",
            "complete_bundle_manifest_sha256",
            "root_manifest_sha256",
            "replay_descriptor_sha256",
        ):
            if not _is_hex64(descriptor.get(key)):
                return False

        unsigned = {key: value for key, value in descriptor.items() if key != "replay_descriptor_sha256"}
        if descriptor.get("replay_descriptor_sha256") != _digest_payload(unsigned):
            return False

        expected = build_pilot_startup_evidence_handoff_replay_descriptor(
            receipt_path, bundle_dir, manifest, extension_chain, evidence
        )
        return dict(descriptor) == expected
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False
