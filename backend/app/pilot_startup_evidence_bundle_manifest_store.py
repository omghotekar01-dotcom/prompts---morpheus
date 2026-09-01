from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_bundle_manifest import (
    verify_pilot_startup_evidence_bundle_manifest,
    verify_pilot_startup_evidence_bundle_manifest_against_stores,
)
from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceBundleManifestStore:
    """Immutable local persistence for verified startup-evidence bundle inventories.

    This store preserves only deterministic digest inventories for independently verified local
    startup-evidence graphs. Canonical persistence and recursive store binding provide local
    completeness/audit/reproduction integrity only. They do not establish wall-clock chronology,
    operator identity, a digital signature, trusted timestamp, externally append-only publication,
    remote attestation, production authorization, security certification, benchmark/performance
    evidence, novelty, or patentability.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(bundle: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8") + b"\n"

    def path_for(self, bundle_manifest_sha256: str) -> Path:
        if (
            not isinstance(bundle_manifest_sha256, str)
            or _HEX64.fullmatch(bundle_manifest_sha256) is None
        ):
            raise ValueError("bundle-manifest digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{bundle_manifest_sha256}.json"

    def persist(
        self,
        bundle: Mapping[str, Any],
        manifest: Mapping[str, Any],
        extension_chain: Mapping[str, Any],
        evidence: Sequence[ExtensionEvidence],
    ) -> Path:
        if not verify_pilot_startup_evidence_bundle_manifest(
            bundle, manifest, extension_chain, evidence
        ):
            raise ValueError("pilot startup evidence bundle manifest failed verification")
        digest = bundle.get("bundle_manifest_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified startup evidence bundle manifest is missing its digest")

        path = self.path_for(digest)
        self.root.mkdir(parents=True, exist_ok=True)
        raw = self._canonical_bytes(bundle)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("bundle-manifest digest collision or on-disk tampering detected")
        return path

    def load(
        self,
        bundle_manifest_sha256: str,
        manifest: Mapping[str, Any],
        extension_chain: Mapping[str, Any],
        evidence: Sequence[ExtensionEvidence],
    ) -> dict[str, Any]:
        path = self.path_for(bundle_manifest_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored bundle manifest is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored bundle manifest must be a JSON object")
        if payload.get("bundle_manifest_sha256") != bundle_manifest_sha256:
            raise ValueError("stored bundle-manifest filename does not match its digest")
        if not verify_pilot_startup_evidence_bundle_manifest(
            payload, manifest, extension_chain, evidence
        ):
            raise ValueError("stored bundle manifest failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored bundle manifest is not canonical JSON")
        return payload

    def verify_against_evidence_stores(
        self,
        bundle_manifest_sha256: str,
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
        """Verify the durable inventory and recursively rebind its complete named evidence graph."""

        try:
            payload = self.load(
                bundle_manifest_sha256, manifest, extension_chain, evidence
            )
            return verify_pilot_startup_evidence_bundle_manifest_against_stores(
                payload,
                manifest,
                extension_chain,
                evidence,
                root_manifest_root,
                extension_chain_root,
                extension_root,
                transition_chain_root,
                transition_root,
                checkpoint_chain_root,
            )
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return False
