from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import (
    ExtensionEvidence,
    verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain,
)
from .pilot_startup_evidence_checkpoint_transition_chain_extension_store import (
    PilotStartupEvidenceCheckpointTransitionChainExtensionStore,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore:
    """Immutable local persistence for verified extension-continuity chains.

    This store preserves deterministic local audit/reproduction evidence across a supplied sequence
    of verified transition-chain extension artifacts. Durable persistence and nested store binding
    do not establish wall-clock chronology, operator identity, a digital signature, trusted
    timestamp, externally append-only publication, remote attestation, security certification,
    production authorization, benchmark or performance evidence, novelty, or patentability.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(artifact: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(artifact),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8") + b"\n"

    def path_for(self, extension_chain_sha256: str) -> Path:
        if (
            not isinstance(extension_chain_sha256, str)
            or _HEX64.fullmatch(extension_chain_sha256) is None
        ):
            raise ValueError("extension-chain digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{extension_chain_sha256}.json"

    def persist(
        self,
        artifact: Mapping[str, Any],
        evidence: Sequence[ExtensionEvidence],
    ) -> Path:
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
            artifact, evidence
        ):
            raise ValueError(
                "pilot startup evidence transition-chain extension chain failed verification"
            )
        digest = artifact.get("extension_chain_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified transition-chain extension chain is missing its digest")

        path = self.path_for(digest)
        self.root.mkdir(parents=True, exist_ok=True)
        raw = self._canonical_bytes(artifact)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError(
                    "transition-chain extension-chain digest collision or on-disk tampering detected"
                )
        return path

    def load(
        self,
        extension_chain_sha256: str,
        evidence: Sequence[ExtensionEvidence],
    ) -> dict[str, Any]:
        path = self.path_for(extension_chain_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "stored transition-chain extension chain is not canonical UTF-8 JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError("stored transition-chain extension chain must be a JSON object")
        if payload.get("extension_chain_sha256") != extension_chain_sha256:
            raise ValueError(
                "stored transition-chain extension-chain filename does not match its digest"
            )
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
            payload, evidence
        ):
            raise ValueError("stored transition-chain extension chain failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored transition-chain extension chain is not canonical JSON")
        return payload

    def verify_against_evidence_stores(
        self,
        extension_chain_sha256: str,
        evidence: Sequence[ExtensionEvidence],
        extension_root: str | Path,
        transition_chain_root: str | Path,
        transition_root: str | Path,
        checkpoint_chain_root: str | Path,
    ) -> bool:
        """Verify the durable extension path and every nested immutable evidence dependency.

        ``evidence`` remains explicit because independent verification requires the full predecessor
        and successor aggregate chains plus their transition evidence. Each named extension must
        exist canonically in the immutable extension store and must itself independently bind through
        aggregate transition chains, transitions, and checkpoint chains.
        """

        try:
            payload = self.load(extension_chain_sha256, evidence)
            expected_digests = payload.get("extension_sha256_chain")
            if not isinstance(expected_digests, list) or len(expected_digests) != len(evidence):
                return False

            extension_store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(
                extension_root
            )
            verified_evidence: list[ExtensionEvidence] = []

            for expected_digest, item in zip(expected_digests, evidence, strict=True):
                extension, previous_chain, previous_evidence, next_chain, next_evidence = item
                if extension.get("extension_sha256") != expected_digest:
                    return False

                stored_extension = extension_store.load(
                    expected_digest,
                    previous_chain,
                    previous_evidence,
                    next_chain,
                    next_evidence,
                )
                if stored_extension != dict(extension):
                    return False
                if not extension_store.verify_against_evidence_stores(
                    expected_digest,
                    previous_chain,
                    previous_evidence,
                    next_chain,
                    next_evidence,
                    transition_chain_root,
                    transition_root,
                    checkpoint_chain_root,
                ):
                    return False

                verified_evidence.append(
                    (
                        stored_extension,
                        previous_chain,
                        previous_evidence,
                        next_chain,
                        next_evidence,
                    )
                )

            return verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
                payload,
                verified_evidence,
            )
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return False
