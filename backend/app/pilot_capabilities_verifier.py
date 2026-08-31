from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .pilot_capabilities import SCHEMA


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_TOP_LEVEL = {
    "schema",
    "declared_scope",
    "production_deployment_authorized",
    "capabilities",
    "operator_surfaces",
    "truth_boundaries",
    "sha256",
}
_REQUIRED_BLOCKED_CAPABILITIES = {
    "automatic_retry_execution_authority": "NOT_GRANTED_BY_EVIDENCE_UTILITIES",
    "native_cross_process_hot_swap": "BLOCKED_NOT_IMPLEMENTED",
    "high_availability_storage": "NOT_IMPLEMENTED_SINGLE_NODE_SQLITE_AND_LOCAL_CAS",
    "multi_tenant_identity_and_authorization": "NOT_IMPLEMENTED_API_KEY_GUARD_ONLY",
}


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_pilot_capabilities(payload: Mapping[str, Any]) -> bool:
    """Fail closed unless the startup/pilot capability ledger is intact and scoped.

    Verification proves only deterministic ledger integrity and preservation of
    explicit safety boundaries. It does not establish production readiness,
    external security review, benchmark superiority, publication acceptance,
    patentability, or customer validation.
    """

    try:
        if not _REQUIRED_TOP_LEVEL <= set(payload):
            return False
        if payload.get("schema") != SCHEMA:
            return False
        if payload.get("declared_scope") != "SINGLE_NODE_ENGINEERING_PILOT":
            return False
        if payload.get("production_deployment_authorized") is not False:
            return False

        digest = payload.get("sha256")
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            return False

        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, Mapping) or not capabilities:
            return False
        if any(not isinstance(key, str) or not key for key in capabilities):
            return False
        if any(not isinstance(value, str) or not value for value in capabilities.values()):
            return False
        for capability, expected_state in _REQUIRED_BLOCKED_CAPABILITIES.items():
            if capabilities.get(capability) != expected_state:
                return False

        operator_surfaces = payload.get("operator_surfaces")
        if not isinstance(operator_surfaces, Mapping) or not operator_surfaces:
            return False
        if any(not isinstance(key, str) or not key for key in operator_surfaces):
            return False
        if any(not isinstance(value, str) or not value for value in operator_surfaces.values()):
            return False

        truth_boundaries = payload.get("truth_boundaries")
        if not isinstance(truth_boundaries, list) or not truth_boundaries:
            return False
        if any(not isinstance(item, str) or not item for item in truth_boundaries):
            return False

        core = dict(payload)
        core.pop("sha256", None)
        return _canonical_sha256(core) == digest
    except (TypeError, ValueError):
        return False
