from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_bundle_manifest import (
    build_pilot_startup_evidence_bundle_manifest,
)
from .pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore
from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_root_manifest_store import PilotStartupEvidenceRootManifestStore

_SCHEMA = "morpheus-pilot-startup-evidence-complete-bundle-manifest-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_COMPLETE_STARTUP_EVIDENCE_BUNDLE_INVENTORY"
_TRUTH_BOUNDARY = (
    "This complete bundle manifest is a deterministic local inventory of the structural startup-"
    "evidence graph plus the historical catalog checkpoints and startup receipts actually referenced "
    "by that graph. Construction and verification require the durable root and every referenced local "
    "artifact to pass their independent verifiers. The manifest inventories content identities only; "
    "it does not copy, publish, sign, timestamp, externally attest, or authorize those bytes, and it "
    "does not establish production deployment approval, security certification, benchmark or "
    "performance evidence, novelty, or patentability."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_STRUCTURAL_KEYS = {
    "checkpoint_chains",
    "transitions",
    "transition_chains",
    "extensions",
    "extension_chains",
    "root_manifests",
}
_COMPLETE_KEYS = _STRUCTURAL_KEYS | {"catalogs", "startup_receipts"}
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "root_manifest_sha256",
    "structural_bundle_manifest_sha256",
    "artifact_digests",
    "artifact_count",
    "production_deployment_authorized",
    "truth_boundary",
    "complete_bundle_manifest_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _referenced_catalog_digests(evidence: Sequence[ExtensionEvidence]) -> list[str]:
    catalogs: set[str] = set()
    for _extension, _previous_chain, previous_evidence, _next_chain, next_evidence in evidence:
        for transition_evidence in (previous_evidence, next_evidence):
            for _transition, left_chain, right_chain in transition_evidence:
                for checkpoint_chain in (left_chain, right_chain):
                    chain_catalogs = checkpoint_chain.get("catalog_sha256_chain")
                    if not isinstance(chain_catalogs, list):
                        raise ValueError("checkpoint chain is missing its catalog digest chain")
                    for digest in chain_catalogs:
                        if not _is_hex64(digest):
                            raise ValueError("checkpoint chain contains an invalid catalog digest")
                        catalogs.add(digest)
    if not catalogs:
        raise ValueError("complete startup evidence graph must reference at least one catalog")
    return sorted(catalogs)


def _complete_inventory(
    structural_bundle: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
    catalog_root: str | Path,
) -> dict[str, list[str]]:
    structural = structural_bundle.get("artifact_digests")
    if not isinstance(structural, Mapping) or set(structural) != _STRUCTURAL_KEYS:
        raise ValueError("structural bundle manifest has an invalid artifact inventory")

    catalog_store = PilotStartupEvidenceCatalogStore(catalog_root)
    catalogs = _referenced_catalog_digests(evidence)
    receipts: set[str] = set()
    for catalog_sha256 in catalogs:
        catalog = catalog_store.load(catalog_sha256)
        for receipt_sha256 in catalog["receipt_digests"]:
            if not _is_hex64(receipt_sha256):
                raise ValueError("catalog contains an invalid startup receipt digest")
            receipts.add(receipt_sha256)
    if not receipts:
        raise ValueError("complete startup evidence graph must reference at least one startup receipt")

    inventory = {key: list(structural[key]) for key in sorted(_STRUCTURAL_KEYS)}
    inventory["catalogs"] = catalogs
    inventory["startup_receipts"] = sorted(receipts)
    return inventory


def build_pilot_startup_evidence_complete_bundle_manifest(
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
    root_manifest_root: str | Path,
    extension_chain_root: str | Path,
    extension_root: str | Path,
    transition_chain_root: str | Path,
    transition_root: str | Path,
    checkpoint_chain_root: str | Path,
    catalog_root: str | Path,
    startup_evidence_root: str | Path,
) -> dict[str, Any]:
    """Inventory the complete durable local startup-evidence closure for one verified root.

    The returned object is an integrity/completeness descriptor only. It deliberately grants no
    deployment, security, chronology, performance, novelty, or patent authority.
    """

    root_sha256 = manifest.get("root_manifest_sha256")
    if not isinstance(root_sha256, str):
        raise ValueError("startup evidence root manifest is missing its digest")
    root_store = PilotStartupEvidenceRootManifestStore(root_manifest_root)
    if not root_store.verify_complete_evidence_graph(
        root_sha256,
        extension_chain,
        evidence,
        extension_chain_root,
        extension_root,
        transition_chain_root,
        transition_root,
        checkpoint_chain_root,
        catalog_root,
        startup_evidence_root,
    ):
        raise ValueError("complete durable startup evidence graph failed verification")

    structural_bundle = build_pilot_startup_evidence_bundle_manifest(
        manifest, extension_chain, evidence
    )
    artifact_digests = _complete_inventory(structural_bundle, evidence, catalog_root)
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "root_manifest_sha256": root_sha256,
        "structural_bundle_manifest_sha256": structural_bundle["bundle_manifest_sha256"],
        "artifact_digests": artifact_digests,
        "artifact_count": sum(len(items) for items in artifact_digests.values()),
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "complete_bundle_manifest_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_complete_bundle_manifest(
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
    catalog_root: str | Path,
    startup_evidence_root: str | Path,
) -> bool:
    """Fail closed unless a complete inventory exactly matches a newly verified durable graph."""

    try:
        if not isinstance(bundle, Mapping) or set(bundle) != _REQUIRED_KEYS:
            return False
        if bundle.get("schema") != _SCHEMA or bundle.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if bundle.get("production_deployment_authorized") is not False:
            return False
        if bundle.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        for key in (
            "root_manifest_sha256",
            "structural_bundle_manifest_sha256",
            "complete_bundle_manifest_sha256",
        ):
            if not _is_hex64(bundle.get(key)):
                return False

        inventory = bundle.get("artifact_digests")
        if not isinstance(inventory, Mapping) or set(inventory) != _COMPLETE_KEYS:
            return False
        for items in inventory.values():
            if not isinstance(items, list) or not items:
                return False
            if not all(_is_hex64(item) for item in items):
                return False
            if items != sorted(items) or len(items) != len(set(items)):
                return False

        artifact_count = bundle.get("artifact_count")
        if isinstance(artifact_count, bool) or not isinstance(artifact_count, int) or artifact_count < 1:
            return False
        if artifact_count != sum(len(items) for items in inventory.values()):
            return False

        expected = build_pilot_startup_evidence_complete_bundle_manifest(
            manifest,
            extension_chain,
            evidence,
            root_manifest_root,
            extension_chain_root,
            extension_root,
            transition_chain_root,
            transition_root,
            checkpoint_chain_root,
            catalog_root,
            startup_evidence_root,
        )
        return dict(bundle) == expected
    except (OSError, RuntimeError, KeyError, TypeError, ValueError):
        return False
