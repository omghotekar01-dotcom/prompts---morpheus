from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain import (
    TransitionEvidence,
    verify_pilot_startup_evidence_checkpoint_transition_chain,
)
from .pilot_startup_evidence_checkpoint_transition_store import (
    PilotStartupEvidenceCheckpointTransitionStore,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCheckpointTransitionChainStore:
    """Immutable local persistence for verified multi-transition continuity artifacts.

    This store preserves deterministic local audit/reproduction evidence for a supplied sequence of
    startup-evidence checkpoint transitions. Durable persistence does not establish wall-clock
    chronology, operator identity, a digital signature, trusted timestamp, externally append-only
    publication, remote attestation, security certification, production authorization, benchmark or
    performance evidence, novelty, or patentability.
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

    def path_for(self, transition_chain_sha256: str) -> Path:
        if (
            not isinstance(transition_chain_sha256, str)
            or _HEX64.fullmatch(transition_chain_sha256) is None
        ):
            raise ValueError("transition-chain digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{transition_chain_sha256}.json"

    def persist(
        self,
        artifact: Mapping[str, Any],
        evidence: Sequence[TransitionEvidence],
    ) -> Path:
        if not verify_pilot_startup_evidence_checkpoint_transition_chain(artifact, evidence):
            raise ValueError("pilot startup evidence checkpoint transition chain failed verification")
        digest = artifact.get("transition_chain_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified checkpoint transition chain is missing its digest")

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
                    "checkpoint transition-chain digest collision or on-disk tampering detected"
                )
        return path

    def load(
        self,
        transition_chain_sha256: str,
        evidence: Sequence[TransitionEvidence],
    ) -> dict[str, Any]:
        path = self.path_for(transition_chain_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored checkpoint transition chain is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored checkpoint transition chain must be a JSON object")
        if payload.get("transition_chain_sha256") != transition_chain_sha256:
            raise ValueError("stored checkpoint transition-chain filename does not match its digest")
        if not verify_pilot_startup_evidence_checkpoint_transition_chain(payload, evidence):
            raise ValueError("stored checkpoint transition chain failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored checkpoint transition chain is not canonical JSON")
        return payload

    def verify_against_evidence_stores(
        self,
        transition_chain_sha256: str,
        evidence: Sequence[TransitionEvidence],
        transition_root: str | Path,
        checkpoint_chain_root: str | Path,
    ) -> bool:
        """Verify the durable path and every named transition against immutable evidence stores.

        ``evidence`` remains explicit because the transition-chain verifier deliberately requires the
        full predecessor/successor chain artifacts rather than trusting identities embedded in the
        aggregate artifact. Each supplied transition must also exist canonically in the immutable
        transition store and independently bind to the immutable checkpoint-chain store.
        """

        try:
            payload = self.load(transition_chain_sha256, evidence)
            transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
            expected_digests = payload.get("transition_sha256_chain")
            if not isinstance(expected_digests, list) or len(expected_digests) != len(evidence):
                return False

            for expected_digest, item in zip(expected_digests, evidence, strict=True):
                transition, previous_chain, next_chain = item
                if transition.get("transition_sha256") != expected_digest:
                    return False
                stored_transition = transition_store.load(
                    expected_digest,
                    previous_chain,
                    next_chain,
                )
                if stored_transition != dict(transition):
                    return False
                if not transition_store.verify_against_chain_store(
                    expected_digest,
                    checkpoint_chain_root,
                ):
                    return False

            return verify_pilot_startup_evidence_checkpoint_transition_chain(payload, evidence)
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return False
