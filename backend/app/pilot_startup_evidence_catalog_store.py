from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .pilot_startup_evidence_catalog import (
    verify_pilot_startup_evidence_catalog,
    verify_pilot_startup_evidence_catalog_against_store,
)
from .pilot_startup_evidence_store import PilotStartupEvidenceStore

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PilotStartupEvidenceCatalogStore:
    """Immutable local checkpoints for verified startup-evidence catalogs.

    This store preserves deterministic inventory snapshots for audit and
    reproduction. It is intentionally local evidence only: persistence here is
    not a digital signature, trusted timestamp, external attestation, security
    certification, production authorization, performance proof, novelty claim,
    or patent evidence.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _canonical_bytes(catalog: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(catalog),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8") + b"\n"

    def path_for(self, catalog_sha256: str) -> Path:
        if not isinstance(catalog_sha256, str) or _HEX64.fullmatch(catalog_sha256) is None:
            raise ValueError("catalog digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{catalog_sha256}.json"

    def persist(self, catalog: Mapping[str, Any]) -> Path:
        if not verify_pilot_startup_evidence_catalog(catalog):
            raise ValueError("pilot startup evidence catalog failed verification")
        digest = catalog.get("catalog_sha256")
        if not isinstance(digest, str):
            raise ValueError("verified catalog is missing catalog digest")
        path = self.path_for(digest)
        self.root.mkdir(parents=True, exist_ok=True)
        raw = self._canonical_bytes(catalog)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            existing = path.read_bytes()
            if existing != raw:
                raise ValueError("catalog checkpoint digest collision or on-disk tampering detected")
        return path

    def load(self, catalog_sha256: str) -> dict[str, Any]:
        path = self.path_for(catalog_sha256)
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored catalog checkpoint is not canonical UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("stored catalog checkpoint must be a JSON object")
        if payload.get("catalog_sha256") != catalog_sha256:
            raise ValueError("stored catalog checkpoint filename does not match catalog digest")
        if not verify_pilot_startup_evidence_catalog(payload):
            raise ValueError("stored catalog checkpoint failed verification")
        if raw != self._canonical_bytes(payload):
            raise ValueError("stored catalog checkpoint is not canonical JSON")
        return payload

    def verify_against_evidence_store(self, catalog_sha256: str, evidence_root: str | Path) -> bool:
        """Require a catalog to equal the current startup-evidence inventory exactly."""

        try:
            catalog = self.load(catalog_sha256)
        except (OSError, ValueError):
            return False
        return verify_pilot_startup_evidence_catalog_against_store(catalog, evidence_root)

    def verify_referenced_receipts_present(
        self,
        catalog_sha256: str,
        evidence_root: str | Path,
    ) -> bool:
        """Require every receipt named by a historical catalog snapshot to remain verifiable.

        Unlike ``verify_against_evidence_store``, this intentionally permits extra receipts in the
        current store. A historical inventory remains meaningful after later append-only local
        evidence is added, but deletion, substitution, corruption, noncanonical bytes, or an
        unverifiable referenced receipt fails closed.
        """

        try:
            catalog = self.load(catalog_sha256)
            evidence_store = PilotStartupEvidenceStore(evidence_root)
            for receipt_sha256 in catalog["receipt_digests"]:
                evidence_store.load(receipt_sha256)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            return False
        return True
