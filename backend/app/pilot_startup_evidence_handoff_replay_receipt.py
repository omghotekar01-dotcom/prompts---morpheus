from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_portable_handoff import (
    verify_pilot_startup_evidence_portable_handoff_semantics,
)

_SCHEMA = "morpheus-pilot-startup-evidence-handoff-replay-receipt-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_TRANSPORTED_SEMANTIC_REPLAY_RECEIPT"
_TRUTH_BOUNDARY = (
    "This receipt records a deterministic local MORPHEUS semantic replay result for one portable "
    "startup-evidence handoff and binds that result to the handoff, complete-bundle, and root-manifest "
    "content identities. It is content-addressed local evidence only. It is not a digital signature, "
    "trusted timestamp, signer/operator identity, external attestation, append-only publication, "
    "production deployment authorization, security certification, benchmark/performance evidence, "
    "novelty evidence, or patentability evidence."
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "handoff_manifest_sha256",
    "complete_bundle_manifest_sha256",
    "root_manifest_sha256",
    "semantic_replay_passed",
    "production_deployment_authorized",
    "truth_boundary",
    "replay_receipt_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _load_json_object(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def build_pilot_startup_evidence_handoff_replay_receipt(
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, Any]:
    """Build a deterministic receipt only after transported semantic replay succeeds.

    The receipt proves only that MORPHEUS's local deterministic verifier accepted the supplied expected
    graph against the transported durable artifacts at receipt-construction time. It deliberately grants
    no external trust, chronology, deployment, security, performance, novelty, or patent authority.
    """

    root = Path(bundle_dir)
    if not verify_pilot_startup_evidence_portable_handoff_semantics(
        root, manifest, extension_chain, evidence
    ):
        raise ValueError("transported startup-evidence semantic replay failed")

    handoff = _load_json_object(root / "handoff-manifest.json")
    complete = _load_json_object(root / "complete-bundle-manifest.json")

    handoff_sha256 = handoff.get("handoff_manifest_sha256")
    complete_sha256 = complete.get("complete_bundle_manifest_sha256")
    root_sha256 = complete.get("root_manifest_sha256")
    if not all(_is_hex64(value) for value in (handoff_sha256, complete_sha256, root_sha256)):
        raise ValueError("handoff semantic replay identities are invalid")
    if manifest.get("root_manifest_sha256") != root_sha256:
        raise ValueError("expected root manifest identity does not match transported complete bundle")

    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "handoff_manifest_sha256": handoff_sha256,
        "complete_bundle_manifest_sha256": complete_sha256,
        "root_manifest_sha256": root_sha256,
        "semantic_replay_passed": True,
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "replay_receipt_sha256": _digest_payload(payload)}


def verify_pilot_startup_evidence_handoff_replay_receipt(
    receipt: Mapping[str, Any],
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> bool:
    """Fail closed unless the receipt exactly matches a fresh transported semantic replay."""

    try:
        if not isinstance(receipt, Mapping) or set(receipt) != _REQUIRED_KEYS:
            return False
        if receipt.get("schema") != _SCHEMA or receipt.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if receipt.get("semantic_replay_passed") is not True:
            return False
        if receipt.get("production_deployment_authorized") is not False:
            return False
        if receipt.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False
        for key in (
            "handoff_manifest_sha256",
            "complete_bundle_manifest_sha256",
            "root_manifest_sha256",
            "replay_receipt_sha256",
        ):
            if not _is_hex64(receipt.get(key)):
                return False

        unsigned = {key: value for key, value in receipt.items() if key != "replay_receipt_sha256"}
        if receipt.get("replay_receipt_sha256") != _digest_payload(unsigned):
            return False

        expected = build_pilot_startup_evidence_handoff_replay_receipt(
            bundle_dir, manifest, extension_chain, evidence
        )
        return dict(receipt) == expected
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False
