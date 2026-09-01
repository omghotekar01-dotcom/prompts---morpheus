from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .pilot_startup_evidence_store import PilotStartupEvidenceStore

SCHEMA = "morpheus-pilot-startup-evidence-catalog-v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_pilot_startup_evidence_catalog(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    store = PilotStartupEvidenceStore(root_path)
    digests: list[str] = []
    if root_path.exists():
        if not root_path.is_dir():
            raise ValueError("startup evidence root must be a directory")
        for entry in sorted(root_path.iterdir(), key=lambda item: item.name):
            match = re.fullmatch(r"([0-9a-f]{64})\.json", entry.name)
            if not entry.is_file() or match is None:
                raise ValueError(f"unexpected entry in startup evidence store: {entry.name}")
            digest = match.group(1)
            store.load(digest)
            digests.append(digest)
    core = {
        "schema": SCHEMA,
        "declared_scope": "SINGLE_NODE_ENGINEERING_PILOT_STARTUP_EVIDENCE_STORE",
        "receipt_count": len(digests),
        "receipt_digests": digests,
        "production_deployment_authorized": False,
        "truth_boundary": "Local deterministic inventory only; not a signature, external attestation, production authorization, security certification, performance proof, novelty claim, or patent evidence.",
    }
    return {**core, "catalog_sha256": _sha256(core)}


def verify_pilot_startup_evidence_catalog(catalog: Mapping[str, Any]) -> bool:
    try:
        expected = {"schema", "declared_scope", "receipt_count", "receipt_digests", "production_deployment_authorized", "truth_boundary", "catalog_sha256"}
        if set(catalog) != expected:
            return False
        if catalog.get("schema") != SCHEMA or catalog.get("declared_scope") != "SINGLE_NODE_ENGINEERING_PILOT_STARTUP_EVIDENCE_STORE":
            return False
        if catalog.get("production_deployment_authorized") is not False:
            return False
        count = catalog.get("receipt_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return False
        digests = catalog.get("receipt_digests")
        if not isinstance(digests, list) or len(digests) != count:
            return False
        if any(not isinstance(item, str) or _HEX64.fullmatch(item) is None for item in digests):
            return False
        if digests != sorted(digests) or len(set(digests)) != len(digests):
            return False
        boundary = catalog.get("truth_boundary")
        if not isinstance(boundary, str) or not boundary:
            return False
        digest = catalog.get("catalog_sha256")
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            return False
        core = dict(catalog)
        core.pop("catalog_sha256")
        return _sha256(core) == digest
    except (TypeError, ValueError):
        return False


def verify_pilot_startup_evidence_catalog_against_store(catalog: Mapping[str, Any], root: str | Path) -> bool:
    if not verify_pilot_startup_evidence_catalog(catalog):
        return False
    try:
        return dict(catalog) == build_pilot_startup_evidence_catalog(root)
    except (OSError, ValueError, RuntimeError):
        return False
