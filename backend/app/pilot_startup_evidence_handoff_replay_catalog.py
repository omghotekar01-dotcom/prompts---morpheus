from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_handoff_replay_descriptor_store import (
    load_pilot_startup_evidence_handoff_replay_descriptor,
)

_SCHEMA = "morpheus-pilot-startup-evidence-handoff-replay-catalog-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_TRANSPORTED_REPLAY_CATALOG"
_TRUTH_BOUNDARY = (
    "This catalog inventories persisted MORPHEUS transported semantic-replay descriptors only after each "
    "descriptor passes fresh local semantic verification against its supplied evidence context. It improves "
    "deterministic local discoverability and audit continuity. It is not a digital signature, trusted timestamp, "
    "signer/operator identity, external attestation, externally append-only publication, production deployment "
    "authorization, security certification, benchmark/performance evidence, novelty evidence, or patentability evidence."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "descriptor_entries",
    "descriptor_count",
    "semantic_replay_required",
    "production_deployment_authorized",
    "truth_boundary",
    "replay_catalog_sha256",
}
_ENTRY_KEYS = {
    "replay_descriptor_sha256",
    "replay_receipt_sha256",
    "handoff_manifest_sha256",
    "complete_bundle_manifest_sha256",
    "root_manifest_sha256",
}


@dataclass(frozen=True)
class ReplayDescriptorContext:
    descriptor_path: str | Path
    receipt_path: str | Path
    bundle_dir: str | Path
    manifest: Mapping[str, Any]
    extension_chain: Mapping[str, Any]
    evidence: Sequence[ExtensionEvidence]


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _verified_entry(context: ReplayDescriptorContext) -> dict[str, str]:
    descriptor = load_pilot_startup_evidence_handoff_replay_descriptor(
        context.descriptor_path,
        context.receipt_path,
        context.bundle_dir,
        context.manifest,
        context.extension_chain,
        context.evidence,
    )
    entry = {key: descriptor[key] for key in _ENTRY_KEYS}
    if not all(_is_hex64(value) for value in entry.values()):
        raise ValueError("verified replay descriptor contains an invalid digest identity")
    return entry


def build_pilot_startup_evidence_handoff_replay_catalog(
    contexts: Sequence[ReplayDescriptorContext],
) -> dict[str, Any]:
    """Build a deterministic catalog from freshly verified persisted replay descriptors.

    Catalog order is digest-defined rather than caller-defined. Duplicate descriptor identities fail closed so a
    caller cannot inflate the inventory by repeating the same locally verified object.
    """

    if not contexts:
        raise ValueError("replay descriptor catalog requires at least one descriptor context")
    entries = [_verified_entry(context) for context in contexts]
    entries.sort(key=lambda item: item["replay_descriptor_sha256"])
    identities = [entry["replay_descriptor_sha256"] for entry in entries]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate replay descriptor identity in catalog")

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "descriptor_entries": entries,
        "descriptor_count": len(entries),
        "semantic_replay_required": True,
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "replay_catalog_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_handoff_replay_catalog(
    catalog: Mapping[str, Any], contexts: Sequence[ReplayDescriptorContext]
) -> bool:
    """Fail closed unless the catalog exactly reconstructs from freshly verified persisted descriptors."""

    try:
        if not isinstance(catalog, Mapping) or set(catalog) != _REQUIRED_KEYS:
            return False
        if catalog.get("schema") != _SCHEMA or catalog.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if catalog.get("semantic_replay_required") is not True:
            return False
        if catalog.get("production_deployment_authorized") is not False:
            return False
        if catalog.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        if not _is_hex64(catalog.get("replay_catalog_sha256")):
            return False
        entries = catalog.get("descriptor_entries")
        if not isinstance(entries, list) or catalog.get("descriptor_count") != len(entries):
            return False
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
                return False
            if not all(_is_hex64(entry.get(key)) for key in _ENTRY_KEYS):
                return False
        unsigned = {key: value for key, value in catalog.items() if key != "replay_catalog_sha256"}
        if catalog.get("replay_catalog_sha256") != _digest_payload(unsigned):
            return False
        expected = build_pilot_startup_evidence_handoff_replay_catalog(contexts)
        return dict(catalog) == expected
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False
