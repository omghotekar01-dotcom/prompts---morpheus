from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .pilot_startup_evidence_checkpoint_chain import (
    verify_pilot_startup_evidence_checkpoint_chain,
    verify_pilot_startup_evidence_checkpoint_chain_against_store,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCheckpointChainStore:
    """Immutable local persistence for verified startup-evidence checkpoint chains.

    Persistence here preserves deterministic local audit/reproduction evidence only. It does not
    provide a digital signature, trusted timestamp, externally append-only log, remote attestation,
    security certification, production authorization, performance proof, novelty claim, or patent
    evidence.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(chain: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(chain),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8") + b"\n"

    def path_for(self, chain_sha256: str) -> Path:
        if not isinstance(chain_sha256, str) or _HEX64.fullmatch(chain_sha256) is None:
            raise ValueError("chain digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{chain_sha256}.json"

    def persist(self, chain: Mapping[str, Any]) -> Path:
        if not verify_pilot_startup_evidence_checkpoint_chain(chain):
            raise ValueError("pilot startup evidence checkpoint chain failed verification")
        digest = chain.get("chain_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified checkpoint chain is missing chain digest")
        path = self.path_for(digest)
        self.root.mkdir(parents=True, exist_ok=True)
        raw = self._canonical_bytes(chain)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("checkpoint chain digest collision or on-disk tampering detected")
        return path

    def load(self, chain_sha256: str) -> dict[str, Any]:
        path = self.path_for(chain_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored checkpoint chain is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored checkpoint chain must be a JSON object")
        if payload.get("chain_sha256") != chain_sha256:
            raise ValueError("stored checkpoint chain filename does not match chain digest")
        if not verify_pilot_startup_evidence_checkpoint_chain(payload):
            raise ValueError("stored checkpoint chain failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored checkpoint chain is not canonical JSON")
        return payload

    def verify_against_catalog_store(self, chain_sha256: str, checkpoint_root: str | Path) -> bool:
        try:
            chain = self.load(chain_sha256)
        except (OSError, ValueError):
            return False
        return verify_pilot_startup_evidence_checkpoint_chain_against_store(chain, checkpoint_root)
