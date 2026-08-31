from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .pilot_capabilities_verifier import verify_pilot_capabilities
from .pilot_readiness_verifier import verify_pilot_readiness


SCHEMA = "morpheus-pilot-startup-evidence-v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_REVISION = re.compile(r"^[0-9a-f]{7,40}$")


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_hex64(name: str, value: Any) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")
    return value


def build_pilot_startup_evidence(
    *,
    capabilities: Mapping[str, Any],
    readiness: Mapping[str, Any],
    launch_plan: Mapping[str, Any],
    source_revision: str,
    api_contract_sha256: str | None = None,
    feature_policy_sha256: str | None = None,
) -> dict[str, Any]:
    """Bind startup-control evidence without widening deployment authority.

    The receipt proves only that a specific set of already-validated local pilot
    inputs were bound together deterministically. It is not a signature, a
    production authorization, a security certification, or performance evidence.
    """

    capabilities_dict = dict(capabilities)
    readiness_dict = dict(readiness)
    launch_plan_dict = dict(launch_plan)

    if not verify_pilot_capabilities(capabilities_dict):
        raise ValueError("pilot capability ledger failed verification")
    if not verify_pilot_readiness(readiness_dict):
        raise ValueError("pilot readiness receipt failed verification")
    if readiness_dict.get("ready") is not True:
        raise ValueError("pilot readiness receipt is valid but not ready")
    if capabilities_dict.get("production_deployment_authorized") is not False:
        raise ValueError("pilot capability ledger must deny production deployment")
    if launch_plan_dict.get("production_deployment_authorized") is not False:
        raise ValueError("pilot launch plan must deny production deployment")

    capability_sha256 = _require_hex64("capability_sha256", capabilities_dict.get("sha256"))
    readiness_sha256 = _require_hex64("readiness_sha256", readiness_dict.get("readiness_sha256"))
    launch_plan_sha256 = _require_hex64("launch_plan_sha256", launch_plan_dict.get("sha256"))

    if not isinstance(source_revision, str) or _SOURCE_REVISION.fullmatch(source_revision) is None:
        raise ValueError("source_revision must be a lowercase 7-40 character hexadecimal git revision")

    fingerprints: dict[str, str] = {}
    if api_contract_sha256 is not None:
        fingerprints["api_contract_sha256"] = _require_hex64("api_contract_sha256", api_contract_sha256)
    if feature_policy_sha256 is not None:
        fingerprints["feature_policy_sha256"] = _require_hex64("feature_policy_sha256", feature_policy_sha256)

    core: dict[str, Any] = {
        "schema": SCHEMA,
        "evidence_state": "BOUND_VERIFIED_SINGLE_NODE_PILOT_STARTUP_INPUTS",
        "source_revision": source_revision,
        "capability_sha256": capability_sha256,
        "readiness_sha256": readiness_sha256,
        "launch_plan_sha256": launch_plan_sha256,
        "fingerprints": fingerprints,
        "production_deployment_authorized": False,
        "truth_boundaries": [
            "This receipt is a deterministic SHA-256 content binding, not a digital signature or external attestation.",
            "It binds startup-control evidence for the declared single-node engineering pilot only.",
            "It does not establish production authorization, a security certification, an SLA, customer validation, performance superiority, publication acceptance, novelty or patentability.",
        ],
    }
    return {**core, "startup_evidence_sha256": _canonical_sha256(core)}


def verify_pilot_startup_evidence(payload: Mapping[str, Any]) -> bool:
    """Fail closed on malformed, widened, replay-ambiguous, or tampered receipts."""

    if not isinstance(payload, Mapping):
        return False
    candidate = dict(payload)
    digest = candidate.pop("startup_evidence_sha256", None)
    if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
        return False
    if set(candidate) != {
        "schema",
        "evidence_state",
        "source_revision",
        "capability_sha256",
        "readiness_sha256",
        "launch_plan_sha256",
        "fingerprints",
        "production_deployment_authorized",
        "truth_boundaries",
    }:
        return False
    if candidate.get("schema") != SCHEMA:
        return False
    if candidate.get("evidence_state") != "BOUND_VERIFIED_SINGLE_NODE_PILOT_STARTUP_INPUTS":
        return False
    if candidate.get("production_deployment_authorized") is not False:
        return False
    source_revision = candidate.get("source_revision")
    if not isinstance(source_revision, str) or _SOURCE_REVISION.fullmatch(source_revision) is None:
        return False
    for key in ("capability_sha256", "readiness_sha256", "launch_plan_sha256"):
        value = candidate.get(key)
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            return False
    fingerprints = candidate.get("fingerprints")
    if not isinstance(fingerprints, dict) or set(fingerprints) - {"api_contract_sha256", "feature_policy_sha256"}:
        return False
    if any(not isinstance(value, str) or _HEX64.fullmatch(value) is None for value in fingerprints.values()):
        return False
    boundaries = candidate.get("truth_boundaries")
    if not isinstance(boundaries, list) or len(boundaries) != 3 or any(not isinstance(item, str) or not item for item in boundaries):
        return False
    return _canonical_sha256(candidate) == digest
