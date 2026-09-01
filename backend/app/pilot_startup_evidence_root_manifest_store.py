from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import (
    ExtensionEvidence,
)
from .pilot_startup_evidence_root_manifest import (
    verify_pilot_startup_evidence_root_manifest,
    verify_pilot_startup_evidence_root_manifest_against_stores,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceRootManifestStore:
    """Immutable local persistence for verified startup-evidence root manifests.

    The store preserves a canonical, content-addressed handoff descriptor for an independently
    verified local startup-evidence graph. Persistence and recursive store binding provide local
    deterministic audit/reproduction integrity only. They do not establish wall-clock chronology,
    operator identity, a digital signature, trusted timestamp, externally append-only publication,
    remote attestation, production authorization, security certification, benchmark or performance
    evidence, novelty, or patentability.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(manifest: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(manifest),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8") + b"\n"

    def path_for(self, root_manifest_sha256: str) -> Path:
        if (
            not isinstance(root_manifest_sha256, str)
            or _HEX64.fullmatch(root_manifest_sha256) is None
        ):
            raise ValueError("root-manifest digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{root_manifest_sha256}.json"

    def persist(
        self,
        manifest: Mapping[str, Any],
        extension_chain: Mapping[str, Any],
        evidence: Sequence[ExtensionEvidence],
    ) -> Path:
        if not verify_pilot_startup_evidence_root_manifest(
            manifest, extension_chain, evidence
        ):
            raise ValueError("pilot startup evidence root manifest failed verification")
        digest = manifest.get("root_manifest_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified startup evidence root manifest is missing its digest")

        path = self.path_for(digest)
        self.root.mkdir(parents=True, exist_ok=True)
        raw = self._canonical_bytes(manifest)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("root-manifest digest collision or on-disk tampering detected")
        return path

    def load(
        self,
        root_manifest_sha256: str,
        extension_chain: Mapping[str, Any],
        evidence: Sequence[ExtensionEvidence],
    ) -> dict[str, Any]:
        path = self.path_for(root_manifest_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored root manifest is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored root manifest must be a JSON object")
        if payload.get("root_manifest_sha256") != root_manifest_sha256:
            raise ValueError("stored root-manifest filename does not match its digest")
        if not verify_pilot_startup_evidence_root_manifest(
            payload, extension_chain, evidence
        ):
            raise ValueError("stored root manifest failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored root manifest is not canonical JSON")
        return payload

    def verify_against_evidence_stores(
        self,
        root_manifest_sha256: str,
        extension_chain: Mapping[str, Any],
        evidence: Sequence[ExtensionEvidence],
        extension_chain_root: str | Path,
        extension_root: str | Path,
        transition_chain_root: str | Path,
        transition_root: str | Path,
        checkpoint_chain_root: str | Path,
    ) -> bool:
        """Verify the durable root and recursively rebind every immutable evidence dependency."""

        try:
            payload = self.load(root_manifest_sha256, extension_chain, evidence)
            return verify_pilot_startup_evidence_root_manifest_against_stores(
                payload,
                extension_chain,
                evidence,
                extension_chain_root,
                extension_root,
                transition_chain_root,
                transition_root,
                checkpoint_chain_root,
            )
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return False
