from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_complete_bundle_manifest import (
    verify_pilot_startup_evidence_complete_bundle_manifest,
)

_SCHEMA = "morpheus-pilot-startup-evidence-portable-handoff-v1"
_EVIDENCE_STATE = "LOCAL_DETERMINISTIC_PORTABLE_STARTUP_EVIDENCE_HANDOFF"
_TRUTH_BOUNDARY = (
    "This handoff materializes byte-for-byte copies of one locally verified complete startup-evidence "
    "closure and binds every copied file to a deterministic SHA-256 inventory. Self-verification proves "
    "only package completeness and byte integrity after export. It does not independently re-establish "
    "the source graph semantics, chronology, operator identity, signatures, trusted timestamps, external "
    "publication, remote attestation, production authorization, security certification, benchmark or "
    "performance evidence, novelty, or patentability."
)
_CATEGORY_ORDER = (
    "checkpoint_chains",
    "transitions",
    "transition_chains",
    "extensions",
    "extension_chains",
    "root_manifests",
    "catalogs",
    "startup_receipts",
)
_REQUIRED_KEYS = {
    "schema",
    "evidence_state",
    "complete_bundle_manifest_sha256",
    "files",
    "file_count",
    "production_deployment_authorized",
    "truth_boundary",
    "handoff_manifest_sha256",
}


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8") + b"\n"


def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return _digest_bytes(_canonical_bytes(payload).rstrip(b"\n"))


def _artifact_roots(
    root_manifest_root: str | Path,
    extension_chain_root: str | Path,
    extension_root: str | Path,
    transition_chain_root: str | Path,
    transition_root: str | Path,
    checkpoint_chain_root: str | Path,
    catalog_root: str | Path,
    startup_evidence_root: str | Path,
) -> dict[str, Path]:
    return {
        "checkpoint_chains": Path(checkpoint_chain_root),
        "transitions": Path(transition_root),
        "transition_chains": Path(transition_chain_root),
        "extensions": Path(extension_root),
        "extension_chains": Path(extension_chain_root),
        "root_manifests": Path(root_manifest_root),
        "catalogs": Path(catalog_root),
        "startup_receipts": Path(startup_evidence_root),
    }


def _safe_relative_file(category: str, digest: str) -> str:
    return f"artifacts/{category}/{digest}.json"


def _build_handoff_manifest(
    complete_bundle_manifest_sha256: str, files: Mapping[str, str]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "evidence_state": _EVIDENCE_STATE,
        "complete_bundle_manifest_sha256": complete_bundle_manifest_sha256,
        "files": dict(sorted(files.items())),
        "file_count": len(files),
        "production_deployment_authorized": False,
        "truth_boundary": _TRUTH_BOUNDARY,
    }
    return {**payload, "handoff_manifest_sha256": _digest_payload(payload)}


def export_pilot_startup_evidence_portable_handoff(
    bundle: Mapping[str, Any],
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
    output_root: str | Path,
    root_manifest_root: str | Path,
    extension_chain_root: str | Path,
    extension_root: str | Path,
    transition_chain_root: str | Path,
    transition_root: str | Path,
    checkpoint_chain_root: str | Path,
    catalog_root: str | Path,
    startup_evidence_root: str | Path,
) -> Path:
    """Materialize a verified complete local evidence closure into a deterministic handoff directory."""

    verification_args = (
        root_manifest_root,
        extension_chain_root,
        extension_root,
        transition_chain_root,
        transition_root,
        checkpoint_chain_root,
        catalog_root,
        startup_evidence_root,
    )
    if not verify_pilot_startup_evidence_complete_bundle_manifest(
        bundle, manifest, extension_chain, evidence, *verification_args
    ):
        raise ValueError("complete startup evidence bundle failed durable-closure verification")

    bundle_digest = bundle.get("complete_bundle_manifest_sha256")
    inventory = bundle.get("artifact_digests")
    if not isinstance(bundle_digest, str) or not isinstance(inventory, Mapping):
        raise ValueError("verified complete bundle is missing its digest inventory")

    roots = _artifact_roots(*verification_args)
    output_root = Path(output_root)
    destination = output_root / bundle_digest
    if destination.exists():
        if verify_pilot_startup_evidence_portable_handoff(destination):
            return destination
        raise ValueError("existing handoff directory is incomplete or has been modified")

    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{bundle_digest}.", dir=output_root))
    try:
        files: dict[str, str] = {}
        complete_rel = "complete-bundle-manifest.json"
        complete_raw = _canonical_bytes(bundle)
        (staging / complete_rel).write_bytes(complete_raw)
        files[complete_rel] = _digest_bytes(complete_raw)

        for category in _CATEGORY_ORDER:
            digests = inventory.get(category)
            if not isinstance(digests, list) or not digests:
                raise ValueError(f"complete bundle has invalid {category} inventory")
            for digest in digests:
                if not isinstance(digest, str):
                    raise ValueError(f"complete bundle has invalid {category} digest")
                source = roots[category] / f"{digest}.json"
                raw = source.read_bytes()
                relative = _safe_relative_file(category, digest)
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                files[relative] = _digest_bytes(raw)

        handoff = _build_handoff_manifest(bundle_digest, files)
        (staging / "handoff-manifest.json").write_bytes(_canonical_bytes(handoff))
        if not verify_pilot_startup_evidence_portable_handoff(staging):
            raise ValueError("newly materialized startup evidence handoff failed self-verification")

        os.replace(staging, destination)
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_pilot_startup_evidence_portable_handoff(bundle_dir: str | Path) -> bool:
    """Verify package completeness and copied-byte integrity without claiming external trust."""

    try:
        root = Path(bundle_dir)
        raw_manifest = (root / "handoff-manifest.json").read_bytes()
        handoff = json.loads(raw_manifest.decode("utf-8"))
        if not isinstance(handoff, dict) or set(handoff) != _REQUIRED_KEYS:
            return False
        if raw_manifest != _canonical_bytes(handoff):
            return False
        if handoff.get("schema") != _SCHEMA or handoff.get("evidence_state") != _EVIDENCE_STATE:
            return False
        if handoff.get("production_deployment_authorized") is not False:
            return False
        if handoff.get("truth_boundary") != _TRUTH_BOUNDARY:
            return False

        digest = handoff.get("complete_bundle_manifest_sha256")
        files = handoff.get("files")
        file_count = handoff.get("file_count")
        handoff_digest = handoff.get("handoff_manifest_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            return False
        if not isinstance(files, dict) or not files:
            return False
        if isinstance(file_count, bool) or not isinstance(file_count, int) or file_count != len(files):
            return False
        if not isinstance(handoff_digest, str):
            return False
        unsigned = {key: value for key, value in handoff.items() if key != "handoff_manifest_sha256"}
        if handoff_digest != _digest_payload(unsigned):
            return False

        required_paths = {"handoff-manifest.json", *files.keys()}
        actual_paths = {
            path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
        }
        if actual_paths != required_paths:
            return False
        if "complete-bundle-manifest.json" not in files:
            return False

        for relative, expected_sha256 in files.items():
            if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
                return False
            if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
                return False
            if _digest_bytes((root / relative).read_bytes()) != expected_sha256:
                return False

        complete_raw = (root / "complete-bundle-manifest.json").read_bytes()
        complete = json.loads(complete_raw.decode("utf-8"))
        if not isinstance(complete, dict) or complete_raw != _canonical_bytes(complete):
            return False
        if complete.get("complete_bundle_manifest_sha256") != digest:
            return False

        inventory = complete.get("artifact_digests")
        if not isinstance(inventory, dict):
            return False
        expected_artifacts = {
            _safe_relative_file(category, item)
            for category in _CATEGORY_ORDER
            for item in inventory.get(category, [])
        }
        return expected_artifacts == (set(files) - {"complete-bundle-manifest.json"})
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return False


def verify_pilot_startup_evidence_portable_handoff_semantics(
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> bool:
    """Re-run complete graph semantics against transported copies after package integrity passes.

    This is a local semantic replay gate. The supplied graph objects identify the expected evidence
    graph, while every durable artifact read by the complete verifier comes from the handoff directory.
    Success proves that the transported copies still satisfy MORPHEUS's existing deterministic local
    evidence contracts. It does not establish signer/operator identity, trusted chronology or timestamps,
    external attestation, append-only publication, production authorization, security certification,
    benchmark/performance superiority, novelty, or patentability.
    """

    try:
        root = Path(bundle_dir)
        if not verify_pilot_startup_evidence_portable_handoff(root):
            return False

        complete_raw = (root / "complete-bundle-manifest.json").read_bytes()
        complete = json.loads(complete_raw.decode("utf-8"))
        if not isinstance(complete, dict):
            return False

        artifacts = root / "artifacts"
        transported_roots = (
            artifacts / "root_manifests",
            artifacts / "extension_chains",
            artifacts / "extensions",
            artifacts / "transition_chains",
            artifacts / "transitions",
            artifacts / "checkpoint_chains",
            artifacts / "catalogs",
            artifacts / "startup_receipts",
        )
        return verify_pilot_startup_evidence_complete_bundle_manifest(
            complete,
            manifest,
            extension_chain,
            evidence,
            *transported_roots,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return False
