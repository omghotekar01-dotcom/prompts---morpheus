from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import (
    ExtensionEvidence,
)
from .pilot_startup_evidence_root_manifest import (
    verify_pilot_startup_evidence_root_manifest,
)
from .pilot_startup_evidence_root_manifest_store import PilotStartupEvidenceRootManifestStore

_SCHEMA = "morpheus-pilot-startup-evidence-bundle-manifest-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_STARTUP_EVIDENCE_BUNDLE_INVENTORY"
_TRUTH_BOUNDARY = (
    "This bundle manifest gives a deterministic inventory of the immutable local startup-evidence "
    "artifacts required by one independently verified root manifest. It supports reproducible local "
    "handoff and completeness checking of the named evidence graph only. It does not package or "
    "publish bytes by itself and does not establish wall-clock chronology, operator identity, a "
    "digital signature, trusted timestamp, externally append-only publication, remote attestation, "
    "production authorization, security certification, benchmark or performance evidence, novelty, "
    "or patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_INVENTORY_KEYS = {
    "checkpoint_chains",
    "transitions",
    "transition_chains",
    "extensions",
    "extension_chains",
    "root_manifests",
}
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "root_manifest_sha256",
    "extension_chain_sha256",
    "artifact_digests",
    "artifact_count",
    "production_deployment_authorized",
    "truth_boundary",
    "bundle_manifest_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _inventory(
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, list[str]]:
    checkpoint_chains: set[str] = set()
    transitions: set[str] = set()
    transition_chains: set[str] = set()
    extensions: set[str] = set()

    for extension, previous_chain, previous_evidence, next_chain, next_evidence in evidence:
        extensions.add(extension["extension_sha256"])
        for transition_chain, transition_evidence in (
            (previous_chain, previous_evidence),
            (next_chain, next_evidence),
        ):
            transition_chains.add(transition_chain["transition_chain_sha256"])
            for transition, left, right in transition_evidence:
                transitions.add(transition["transition_sha256"])
                checkpoint_chains.add(left["chain_sha256"])
                checkpoint_chains.add(right["chain_sha256"])

    return {
        "checkpoint_chains": sorted(checkpoint_chains),
        "transitions": sorted(transitions),
        "transition_chains": sorted(transition_chains),
        "extensions": sorted(extensions),
        "extension_chains": [extension_chain["extension_chain_sha256"]],
        "root_manifests": [manifest["root_manifest_sha256"]],
    }


def build_pilot_startup_evidence_bundle_manifest(
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, Any]:
    """Build a deterministic complete inventory for one verified local startup-evidence graph."""

    if not verify_pilot_startup_evidence_root_manifest(manifest, extension_chain, evidence):
        raise ValueError("startup evidence root manifest failed verification")

    artifact_digests = _inventory(manifest, extension_chain, evidence)
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "root_manifest_sha256": manifest["root_manifest_sha256"],
        "extension_chain_sha256": extension_chain["extension_chain_sha256"],
        "artifact_digests": artifact_digests,
        "artifact_count": sum(len(items) for items in artifact_digests.values()),
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "bundle_manifest_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_bundle_manifest(
    bundle: Mapping[str, Any],
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> bool:
    """Verify a deterministic evidence inventory against independently verified supplied evidence."""

    try:
        if not isinstance(bundle, Mapping) or set(bundle) != _REQUIRED_KEYS:
            return False
        if bundle.get("schema") != _SCHEMA or bundle.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if bundle.get("production_deployment_authorized") is not False:
            return False
        if bundle.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        if not verify_pilot_startup_evidence_root_manifest(manifest, extension_chain, evidence):
            return False

        for key in ("root_manifest_sha256", "extension_chain_sha256", "bundle_manifest_sha256"):
            if not _is_hex64(bundle.get(key)):
                return False
        if bundle["root_manifest_sha256"] != manifest["root_manifest_sha256"]:
            return False
        if bundle["extension_chain_sha256"] != extension_chain["extension_chain_sha256"]:
            return False

        inventory = bundle.get("artifact_digests")
        if not isinstance(inventory, Mapping) or set(inventory) != _INVENTORY_KEYS:
            return False
        for items in inventory.values():
            if not isinstance(items, list) or not items:
                return False
            if not all(_is_hex64(item) for item in items):
                return False
            if items != sorted(items) or len(set(items)) != len(items):
                return False

        expected = _inventory(manifest, extension_chain, evidence)
        if dict(inventory) != expected:
            return False

        artifact_count = bundle.get("artifact_count")
        if isinstance(artifact_count, bool) or not isinstance(artifact_count, int) or artifact_count < 1:
            return False
        if artifact_count != sum(len(items) for items in expected.values()):
            return False

        unsigned = {key: bundle[key] for key in _REQUIRED_KEYS if key != "bundle_manifest_sha256"}
        return bundle["bundle_manifest_sha256"] == _digest_payload(unsigned)
    except (IndexError, KeyError, TypeError, ValueError):
        return False


def verify_pilot_startup_evidence_bundle_manifest_against_stores(
    bundle: Mapping[str, Any],
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
    root_manifest_root: str | Path,
    extension_chain_root: str | Path,
    extension_root: str | Path,
    transition_chain_root: str | Path,
    transition_root: str | Path,
    checkpoint_chain_root: str | Path,
) -> bool:
    """Verify the inventory and recursively rebind its persisted root through all local stores."""

    try:
        if not verify_pilot_startup_evidence_bundle_manifest(
            bundle, manifest, extension_chain, evidence
        ):
            return False

        store = PilotStartupEvidenceRootManifestStore(root_manifest_root)
        digest = bundle.get("root_manifest_sha256")
        if not isinstance(digest, str):
            return False
        stored_manifest = store.load(digest, extension_chain, evidence)
        if stored_manifest != dict(manifest):
            return False

        return store.verify_against_evidence_stores(
            digest,
            extension_chain,
            evidence,
            extension_chain_root,
            extension_root,
            transition_chain_root,
            transition_root,
            checkpoint_chain_root,
        )
    except (OSError, ValueError, TypeError):
        return False
