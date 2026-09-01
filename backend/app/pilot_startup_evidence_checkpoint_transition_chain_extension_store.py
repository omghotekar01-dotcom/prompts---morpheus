from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain import TransitionEvidence
from .pilot_startup_evidence_checkpoint_transition_chain_extension import (
    verify_pilot_startup_evidence_checkpoint_transition_chain_extension,
)
from .pilot_startup_evidence_checkpoint_transition_chain_store import (
    PilotStartupEvidenceCheckpointTransitionChainStore,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCheckpointTransitionChainExtensionStore:
    """Immutable local persistence for verified transition-chain extension artifacts.

    This store preserves deterministic local audit/reproduction evidence that one verified startup-
    evidence transition chain is an exact one-transition structural extension of another. Durable
    persistence and nested store binding do not establish wall-clock chronology, operator identity,
    a digital signature, trusted timestamp, externally append-only publication, remote attestation,
    security certification, production authorization, benchmark or performance evidence, novelty,
    or patentability.
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

    def path_for(self, extension_sha256: str) -> Path:
        if not isinstance(extension_sha256, str) or _HEX64.fullmatch(extension_sha256) is None:
            raise ValueError("extension digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{extension_sha256}.json"

    def persist(
        self,
        artifact: Mapping[str, Any],
        previous_chain: Mapping[str, Any],
        previous_evidence: Sequence[TransitionEvidence],
        next_chain: Mapping[str, Any],
        next_evidence: Sequence[TransitionEvidence],
    ) -> Path:
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
            artifact,
            previous_chain,
            previous_evidence,
            next_chain,
            next_evidence,
        ):
            raise ValueError("pilot startup evidence transition-chain extension failed verification")
        digest = artifact.get("extension_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified transition-chain extension is missing its digest")

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
                    "transition-chain extension digest collision or on-disk tampering detected"
                )
        return path

    def load(
        self,
        extension_sha256: str,
        previous_chain: Mapping[str, Any],
        previous_evidence: Sequence[TransitionEvidence],
        next_chain: Mapping[str, Any],
        next_evidence: Sequence[TransitionEvidence],
    ) -> dict[str, Any]:
        path = self.path_for(extension_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored transition-chain extension is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored transition-chain extension must be a JSON object")
        if payload.get("extension_sha256") != extension_sha256:
            raise ValueError("stored transition-chain extension filename does not match its digest")
        if not verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
            payload,
            previous_chain,
            previous_evidence,
            next_chain,
            next_evidence,
        ):
            raise ValueError("stored transition-chain extension failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored transition-chain extension is not canonical JSON")
        return payload

    def verify_against_evidence_stores(
        self,
        extension_sha256: str,
        previous_chain: Mapping[str, Any],
        previous_evidence: Sequence[TransitionEvidence],
        next_chain: Mapping[str, Any],
        next_evidence: Sequence[TransitionEvidence],
        transition_chain_root: str | Path,
        transition_root: str | Path,
        checkpoint_chain_root: str | Path,
    ) -> bool:
        """Verify the durable extension plus both aggregate chains and all nested evidence.

        The predecessor/successor aggregate chains remain explicit inputs because independent
        verification requires their full transition evidence. The immutable aggregate-chain store
        must contain canonical copies equal to those supplied artifacts, and each aggregate must in
        turn verify against the immutable transition and checkpoint-chain stores.
        """

        try:
            payload = self.load(
                extension_sha256,
                previous_chain,
                previous_evidence,
                next_chain,
                next_evidence,
            )
            chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(transition_chain_root)

            previous_digest = payload.get("previous_transition_chain_sha256")
            next_digest = payload.get("next_transition_chain_sha256")
            if not isinstance(previous_digest, str) or not isinstance(next_digest, str):
                return False

            stored_previous = chain_store.load(previous_digest, previous_evidence)
            stored_next = chain_store.load(next_digest, next_evidence)
            if stored_previous != dict(previous_chain) or stored_next != dict(next_chain):
                return False

            if not chain_store.verify_against_evidence_stores(
                previous_digest,
                previous_evidence,
                transition_root,
                checkpoint_chain_root,
            ):
                return False
            if not chain_store.verify_against_evidence_stores(
                next_digest,
                next_evidence,
                transition_root,
                checkpoint_chain_root,
            ):
                return False

            return verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
                payload,
                stored_previous,
                previous_evidence,
                stored_next,
                next_evidence,
            )
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return False
