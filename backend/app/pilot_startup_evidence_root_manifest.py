from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore
from .pilot_startup_evidence_checkpoint_chain_store import PilotStartupEvidenceCheckpointChainStore
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
    manifest: Mapping[str, Any], extension_chain: Mapping[str, Any], evidence: Sequence[ExtensionEvidence]
) -> bool:
    try:
        if not isinstance(manifest, Mapping) or set(manifest) != _REQUIRED_KEYS:
            return False
        if manifest.get("schema") != _SCHEMA or manifest.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if manifest.get("production_deployment_authorized") is not False or manifest.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(extension_chain, evidence):
            return False
        for key in ("extension_chain_sha256", "starting_transition_chain_sha256", "ending_transition_chain_sha256", "root_manifest_sha256"):
            if not _is_hex64(manifest.get(key)):
                return False
        for key in ("extension_count", "starting_transition_count", "ending_transition_count"):
            value = manifest.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return False
        bindings = ("extension_chain_sha256", "extension_count", "starting_transition_chain_sha256", "ending_transition_chain_sha256", "starting_transition_count", "ending_transition_count")
        if any(manifest[key] != extension_chain[key] for key in bindings):
            return False
        unsigned = {key: manifest[key] for key in _REQUIRED_KEYS if key != "root_manifest_sha256"}
        return manifest["root_manifest_sha256"] == _digest_payload(unsigned)
    except (KeyError, TypeError, ValueError):
        return False


def verify_pilot_startup_evidence_root_manifest_against_stores(
    manifest: Mapping[str, Any], extension_chain: Mapping[str, Any], evidence: Sequence[ExtensionEvidence],
    extension_chain_root: str | Path, extension_root: str | Path, transition_chain_root: str | Path,
    transition_root: str | Path, checkpoint_chain_root: str | Path,
) -> bool:
    """Rebind the root through structural stores down to checkpoint-chain artifacts."""
    try:
        if not verify_pilot_startup_evidence_root_manifest(manifest, extension_chain, evidence):
            return False
        digest = manifest.get("extension_chain_sha256")
        if not isinstance(digest, str):
            return False
        store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(extension_chain_root)
        stored_extension_chain = store.load(digest, evidence)
        if stored_extension_chain != dict(extension_chain):
            return False
        return store.verify_against_evidence_stores(digest, evidence, extension_root, transition_chain_root, transition_root, checkpoint_chain_root)
    except (OSError, ValueError, TypeError):
        return False


def verify_pilot_startup_evidence_root_manifest_complete_graph(
    manifest: Mapping[str, Any], extension_chain: Mapping[str, Any], evidence: Sequence[ExtensionEvidence],
    extension_chain_root: str | Path, extension_root: str | Path, transition_chain_root: str | Path,
    transition_root: str | Path, checkpoint_chain_root: str | Path, catalog_root: str | Path,
    startup_evidence_root: str | Path,
) -> bool:
    """Verify the root through catalogs to every startup receipt referenced by the history.

    Historical catalog snapshots may be strict subsets of the current receipt store. Later local
    receipts therefore do not invalidate old snapshots, while deletion, substitution, corruption,
    or unverifiable bytes anywhere in the referenced graph fail closed.
    """
    try:
        if not verify_pilot_startup_evidence_root_manifest_against_stores(
            manifest, extension_chain, evidence, extension_chain_root, extension_root,
            transition_chain_root, transition_root, checkpoint_chain_root,
        ):
            return False
        checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root)
        catalog_store = PilotStartupEvidenceCatalogStore(catalog_root)
        seen_checkpoint_chains: set[str] = set()
        seen_catalogs: set[str] = set()
        for _extension, _previous_chain, previous_evidence, _next_chain, next_evidence in evidence:
            for transition_evidence in (previous_evidence, next_evidence):
                for _transition, left_chain, right_chain in transition_evidence:
                    for supplied_chain in (left_chain, right_chain):
                        chain_sha256 = supplied_chain.get("chain_sha256")
                        if not isinstance(chain_sha256, str):
                            return False
                        if chain_sha256 in seen_checkpoint_chains:
                            continue
                        stored_chain = checkpoint_store.load(chain_sha256)
                        if stored_chain != dict(supplied_chain):
                            return False
                        if not checkpoint_store.verify_against_catalog_store(chain_sha256, catalog_root):
                            return False
                        for catalog_sha256 in stored_chain["catalog_sha256_chain"]:
                            if catalog_sha256 in seen_catalogs:
                                continue
                            if not catalog_store.verify_referenced_receipts_present(catalog_sha256, startup_evidence_root):
                                return False
                            seen_catalogs.add(catalog_sha256)
                        seen_checkpoint_chains.add(chain_sha256)
        return bool(seen_checkpoint_chains) and bool(seen_catalogs)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        return False
