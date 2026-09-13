from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from collections.abc import Mapping
from typing import Any


SCHEMA = "morpheus-startup-mvp-readiness-evidence-v1"
READINESS_SCHEMA = "morpheus-startup-mvp-readiness-v1"
EVIDENCE_STATE = "STARTUP_MVP_READINESS_REPLAYABLE_LOCAL_EVIDENCE"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value.lower())


def _verified_readiness(readiness: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(readiness))
    if payload.get("schema") != READINESS_SCHEMA:
        raise ValueError("unsupported startup readiness schema")

    readiness_sha256 = payload.get("readiness_sha256")
    if not _is_sha256(readiness_sha256):
        raise ValueError("startup readiness digest is missing or malformed")

    core = {key: value for key, value in payload.items() if key != "readiness_sha256"}
    if _canonical_sha256(core) != readiness_sha256:
        raise ValueError("startup readiness digest does not match the canonical payload")

    scope = payload.get("scope")
    if not isinstance(scope, Mapping):
        raise ValueError("startup readiness scope is missing")
    if scope.get("production_deployment_authorized") is not False:
        raise ValueError("startup readiness evidence cannot authorize production deployment")
    if scope.get("automatic_control_allowed") is not False:
        raise ValueError("startup readiness evidence cannot authorize automatic control")
    return payload


def build_startup_readiness_evidence(readiness: Mapping[str, Any]) -> dict[str, Any]:
    """Bind one exact startup-readiness result into deterministic replay evidence.

    This envelope is content-addressed engineering evidence only. It is not a
    signature, freshness proof, remote attestation, activation token or
    production authorization.
    """

    verified = _verified_readiness(readiness)
    readiness_sha256 = str(verified["readiness_sha256"])
    core = {
        "schema": SCHEMA,
        "evidence_state": EVIDENCE_STATE,
        "readiness_sha256": readiness_sha256,
        "readiness": verified,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "The evidence envelope is a deterministic content binding over one local startup-readiness payload; it is not a signature, MAC, trusted timestamp, freshness proof or remote attestation.",
            "Successful replay proves internal payload/digest consistency only and does not establish external production reliability, security certification or scientific validity.",
            "The envelope cannot authorize production deployment, activation or automatic control.",
        ],
    }
    return {**core, "evidence_sha256": _canonical_sha256(core)}


def verify_startup_readiness_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless an evidence envelope exactly replays its content identities."""

    payload = deepcopy(dict(evidence))
    if payload.get("schema") != SCHEMA:
        raise ValueError("unsupported startup readiness evidence schema")
    if payload.get("evidence_state") != EVIDENCE_STATE:
        raise ValueError("unexpected startup readiness evidence state")

    readiness = payload.get("readiness")
    if not isinstance(readiness, Mapping):
        raise ValueError("startup readiness payload is missing from evidence")
    verified_readiness = _verified_readiness(readiness)
    if payload.get("readiness_sha256") != verified_readiness.get("readiness_sha256"):
        raise ValueError("evidence readiness digest does not match embedded readiness")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        raise ValueError("startup readiness evidence authority boundary is missing")
    if any(
        authority.get(field) is not False
        for field in (
            "production_deployment_authorized",
            "automatic_control_allowed",
            "activation_allowed",
        )
    ):
        raise ValueError("startup readiness evidence cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness evidence truth boundaries are missing")

    evidence_sha256 = payload.get("evidence_sha256")
    if not _is_sha256(evidence_sha256):
        raise ValueError("startup readiness evidence digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "evidence_sha256"}
    if _canonical_sha256(core) != evidence_sha256:
        raise ValueError("startup readiness evidence digest does not match the canonical envelope")
    return payload
