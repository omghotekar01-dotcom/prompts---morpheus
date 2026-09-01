from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .pilot_startup_evidence_checkpoint_chain_store import (
    PilotStartupEvidenceCheckpointChainStore,
)
from .pilot_startup_evidence_checkpoint_transition import (
    verify_pilot_startup_evidence_checkpoint_transition,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCheckpointTransitionStore:
    """Immutable local persistence for verified checkpoint-chain transition receipts.

    This store preserves deterministic local continuity evidence only. Persistence does not create
    wall-clock chronology, operator identity, a digital signature, trusted timestamp, externally
    append-only publication, remote attestation, security certification, production authorization,
    performance evidence, novelty evidence, or patent evidence.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(transition: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(transition),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8") + b"\n"

    def path_for(self, transition_sha256: str) -> Path:
        if not isinstance(transition_sha256, str) or _HEX64.fullmatch(transition_sha256) is None:
            raise ValueError("transition digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{transition_sha256}.json"

    def persist(
        self,
        transition: Mapping[str, Any],
        previous_chain: Mapping[str, Any],
        next_chain: Mapping[str, Any],
    ) -> Path:
        if not verify_pilot_startup_evidence_checkpoint_transition(
            transition, previous_chain, next_chain
        ):
            raise ValueError("pilot startup evidence checkpoint transition failed verification")
        digest = transition.get("transition_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified checkpoint transition is missing transition digest")

        path = self.path_for(digest)
        self.root.mkdir(parents=True, exist_ok=True)
        raw = self._canonical_bytes(transition)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("checkpoint transition digest collision or on-disk tampering detected")
        return path

    def load(
        self,
        transition_sha256: str,
        previous_chain: Mapping[str, Any],
        next_chain: Mapping[str, Any],
    ) -> dict[str, Any]:
        path = self.path_for(transition_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored checkpoint transition is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored checkpoint transition must be a JSON object")
        if payload.get("transition_sha256") != transition_sha256:
            raise ValueError("stored checkpoint transition filename does not match transition digest")
        if not verify_pilot_startup_evidence_checkpoint_transition(
            payload, previous_chain, next_chain
        ):
            raise ValueError("stored checkpoint transition failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored checkpoint transition is not canonical JSON")
        return payload

    def verify_against_chain_store(
        self,
        transition_sha256: str,
        chain_root: str | Path,
    ) -> bool:
        """Verify a stored transition against both immutable chain artifacts it names."""

        try:
            path = self.path_for(transition_sha256)
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return False
            if payload.get("transition_sha256") != transition_sha256:
                return False
            if raw != self._canonical_bytes(payload):
                return False

            previous_digest = payload.get("previous_chain_sha256")
            next_digest = payload.get("next_chain_sha256")
            if not isinstance(previous_digest, str) or not isinstance(next_digest, str):
                return False

            chain_store = PilotStartupEvidenceCheckpointChainStore(chain_root)
            previous_chain = chain_store.load(previous_digest)
            next_chain = chain_store.load(next_digest)
            return verify_pilot_startup_evidence_checkpoint_transition(
                payload, previous_chain, next_chain
            )
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return False
