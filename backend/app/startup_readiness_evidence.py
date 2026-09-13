from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from collections.abc import Mapping
from typing import Any


SCHEMA = "morpheus-startup-mvp-readiness-evidence-v1"
READINESS_SCHEMA = "morpheus-startup-mvp-readiness-v1"
EVIDENCE_STATE = "STARTUP_MVP_READINESS_REPLAYABLE_LOCAL_EVIDENCE"
CURRENT_COHERENCE_SCHEMA = "morpheus-startup-mvp-readiness-current-coherence-v1"
CURRENT_COHERENT_STATE = "STARTUP_MVP_READINESS_CURRENT_COHERENT"
CURRENT_DRIFTED_STATE = "STARTUP_MVP_READINESS_CURRENT_DRIFTED"


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


def compare_startup_readiness_evidence_to_current(
    evidence: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare valid replay evidence with one freshly composed local readiness result.

    A coherent result means only that the content-addressed evidence and the
    supplied current readiness payload are identical at comparison time. It is
    not an authenticity, freshness, attestation, deployment or control grant.
    """

    verified_evidence = verify_startup_readiness_evidence(evidence)
    embedded = _verified_readiness(verified_evidence["readiness"])
    current = _verified_readiness(current_readiness)

    drifted_sections = [
        section
        for section in ("compatibility", "environment", "scope")
        if _canonical_sha256(embedded.get(section)) != _canonical_sha256(current.get(section))
    ]
    matches_current = embedded["readiness_sha256"] == current["readiness_sha256"]
    if not matches_current and not drifted_sections:
        drifted_sections.append("readiness_payload")

    core = {
        "schema": CURRENT_COHERENCE_SCHEMA,
        "evidence_state": CURRENT_COHERENT_STATE if matches_current else CURRENT_DRIFTED_STATE,
        "matches_current": matches_current,
        "evidence_sha256": verified_evidence["evidence_sha256"],
        "embedded_readiness_sha256": embedded["readiness_sha256"],
        "current_readiness_sha256": current["readiness_sha256"],
        "drifted_sections": drifted_sections,
        "authority": {
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
            "activation_allowed": False,
        },
        "truth_boundaries": [
            "Current-state coherence compares two deterministic local content identities; it is not a signature, freshness oracle, trusted timestamp or remote attestation.",
            "A matching result does not authorize production deployment, activation or automatic control and does not establish external reliability or security certification.",
            "A drifted result means the replayable envelope no longer matches the supplied current readiness payload; it does not identify intent, cause or wall-clock age.",
            "The coherence digest is a replayable content identity only; it does not make the report authentic, fresh, externally trusted or authoritative.",
        ],
    }
    return {**core, "coherence_sha256": _canonical_sha256(core)}


def verify_startup_readiness_current_coherence(report: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless a coherence report is replayable and semantically consistent.

    Replay verifies deterministic local content and declared coherence semantics
    only. It is not authenticity, freshness, attestation or deployment/control
    authority.
    """

    payload = deepcopy(dict(report))
    if payload.get("schema") != CURRENT_COHERENCE_SCHEMA:
        raise ValueError("unsupported startup readiness coherence schema")

    matches_current = payload.get("matches_current")
    if not isinstance(matches_current, bool):
        raise ValueError("startup readiness coherence match flag is missing")

    expected_state = CURRENT_COHERENT_STATE if matches_current else CURRENT_DRIFTED_STATE
    if payload.get("evidence_state") != expected_state:
        raise ValueError("startup readiness coherence state disagrees with match flag")

    for field in ("evidence_sha256", "embedded_readiness_sha256", "current_readiness_sha256"):
        if not _is_sha256(payload.get(field)):
            raise ValueError(f"startup readiness coherence {field} is missing or malformed")

    drifted_sections = payload.get("drifted_sections")
    allowed_sections = {"compatibility", "environment", "scope", "readiness_payload"}
    if not isinstance(drifted_sections, list) or not all(
        isinstance(section, str) and section in allowed_sections for section in drifted_sections
    ):
        raise ValueError("startup readiness coherence drift classification is malformed")
    if len(drifted_sections) != len(set(drifted_sections)):
        raise ValueError("startup readiness coherence drift classification contains duplicates")

    embedded_digest = payload["embedded_readiness_sha256"]
    current_digest = payload["current_readiness_sha256"]
    if matches_current:
        if embedded_digest != current_digest or drifted_sections:
            raise ValueError("coherent report has inconsistent readiness identities or drift classification")
    else:
        if embedded_digest == current_digest or not drifted_sections:
            raise ValueError("drifted report has inconsistent readiness identities or drift classification")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        raise ValueError("startup readiness coherence authority boundary is missing")
    if any(
        authority.get(field) is not False
        for field in (
            "production_deployment_authorized",
            "automatic_control_allowed",
            "activation_allowed",
        )
    ):
        raise ValueError("startup readiness coherence cannot carry activation authority")

    boundaries = payload.get("truth_boundaries")
    if not isinstance(boundaries, list) or not boundaries or not all(isinstance(item, str) and item for item in boundaries):
        raise ValueError("startup readiness coherence truth boundaries are missing")

    coherence_sha256 = payload.get("coherence_sha256")
    if not _is_sha256(coherence_sha256):
        raise ValueError("startup readiness coherence digest is missing or malformed")
    core = {key: value for key, value in payload.items() if key != "coherence_sha256"}
    if _canonical_sha256(core) != coherence_sha256:
        raise ValueError("startup readiness coherence digest does not match canonical report")
    return payload
