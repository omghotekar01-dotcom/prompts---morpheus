from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .pilot_startup_evidence import verify_pilot_startup_evidence


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceStore:
    """Immutable content-addressed storage for verified pilot startup receipts.

    Persistence is an audit/reproduction aid only. A stored receipt is not a
    signature, production authorization, security certification, deployment
    approval, performance proof, or external attestation.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(receipt: Mapping[str, Any]) -> bytes:
        return (
            json.dumps(dict(receipt), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _digest(receipt: Mapping[str, Any]) -> str:
        digest = receipt.get("startup_evidence_sha256")
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            raise ValueError("startup_evidence_sha256 must be a lowercase 64-character digest")
        return digest

    def path_for(self, digest: str) -> Path:
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            raise ValueError("digest must be a lowercase 64-character SHA-256 value")
        return self.root / f"{digest}.json"

    def persist(self, receipt: Mapping[str, Any]) -> Path:
        candidate = dict(receipt)
        if not verify_pilot_startup_evidence(candidate):
            raise ValueError("pilot startup evidence failed verification")
        if candidate.get("production_deployment_authorized") is not False:
            raise ValueError("pilot startup evidence must deny production deployment")

        digest = self._digest(candidate)
        target = self.path_for(digest)
        payload = self._canonical_bytes(candidate)
        self.root.mkdir(parents=True, exist_ok=True)

        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = target.read_bytes()
            if existing != payload:
                raise RuntimeError("startup evidence digest collision or on-disk tampering detected")
            loaded = self.load(digest)
            if loaded != candidate:
                raise RuntimeError("existing startup evidence receipt failed identity verification")
            return target

        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                target.unlink(missing_ok=True)
            finally:
                raise
        return target

    def load(self, digest: str) -> dict[str, Any]:
        path = self.path_for(digest)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored startup evidence is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored startup evidence must be a JSON object")
        if payload.get("startup_evidence_sha256") != digest:
            raise ValueError("stored startup evidence filename does not match receipt digest")
        if not verify_pilot_startup_evidence(payload):
            raise ValueError("stored pilot startup evidence failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored pilot startup evidence is not canonical JSON")
        return payload
