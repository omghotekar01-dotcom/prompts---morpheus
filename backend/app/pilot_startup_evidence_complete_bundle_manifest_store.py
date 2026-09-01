from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_complete_bundle_manifest import (
    verify_pilot_startup_evidence_complete_bundle_manifest,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCompleteBundleManifestStore:
    """Immutable local persistence for verified complete startup-evidence inventories.

    Persistence is content-addressed and verification rebinds the descriptor to the complete durable
    local graph, including referenced historical catalogs and startup receipts. These guarantees are
    local integrity/completeness/audit/reproduction properties only. They do not establish chronology,
    operator identity, signatures, trusted timestamps, external append-only publication, remote
    attestation, production authorization, security certification, benchmark/performance evidence,
    novelty, or patentability.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(bundle: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8") + b"\n"

    def path_for(self, complete_bundle_manifest_sha256: str) -> Path:
        if (
            not isinstance(complete_bundle_manifest_sha256, str)
            or _HEX64.fullmatch(complete_bundle_manifest_sha256) is None
        ):
            raise ValueError(
                "complete-bundle-manifest digest must be 64 lowercase hexadecimal characters"
            )
        return self.root / f"{complete_bundle_manifest_sha256}.json"

    def persist(
        self,
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
    ) -> Path:
        if not verify_pilot_startup_evidence_complete_bundle_manifest(
            bundle,
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
        ):
            raise ValueError("complete startup evidence bundle manifest failed verification")
        digest = bundle.get("complete_bundle_manifest_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified complete startup evidence bundle manifest is missing its digest")

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
                raise ValueError(
                    "complete-bundle-manifest digest collision or on-disk tampering detected"
                )
        return path

    def load(
        self,
        complete_bundle_manifest_sha256: str,
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
        path = self.path_for(complete_bundle_manifest_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored complete bundle manifest is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored complete bundle manifest must be a JSON object")
        if payload.get("complete_bundle_manifest_sha256") != complete_bundle_manifest_sha256:
            raise ValueError("stored complete-bundle-manifest filename does not match its digest")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored complete bundle manifest is not canonical JSON")
        if not verify_pilot_startup_evidence_complete_bundle_manifest(
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
            catalog_root,
            startup_evidence_root,
        ):
            raise ValueError("stored complete bundle manifest failed durable graph verification")
        return payload

    def verify_durable_closure(
        self,
        complete_bundle_manifest_sha256: str,
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
        """Return false unless the stored descriptor and its complete local closure still verify."""

        try:
            self.load(
                complete_bundle_manifest_sha256,
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
            return True
        except (OSError, TypeError, ValueError):
            return False
