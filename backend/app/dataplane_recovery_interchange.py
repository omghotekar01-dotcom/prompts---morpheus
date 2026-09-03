"""Canonical byte-level interchange for MORPHEUS P58 recovery checkpoints.

P59 gives the P58 quiescent active-route checkpoint a strict UTF-8 JSON
interchange contract suitable for caller-managed process boundaries. It does not
write files, provide durability, restore native objects, or imply HA semantics.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .dataplane_recovery import ActiveRouteIdentity, CHECKPOINT_SCHEMA, DataPlaneRecoveryCheckpoint

INTERCHANGE_SCHEMA = "morpheus.dataplane-recovery-interchange/v1"
EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_INTERCHANGE_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only deterministic canonical byte interchange and strict reconstruction of a valid P58 "
    "quiescent active-route checkpoint. It does not provide storage durability, crash consistency, native-object "
    "serialization, staged-migration recovery, rollback-stack recovery, reader-lease recovery, distributed "
    "coordination, cross-process hot swap, production readiness or performance evidence."
)


def _canonical_json_bytes(payload: object) -> bytes:
    # Match P58's json.dumps defaults exactly, including ensure_ascii=True, so
    # valid P58 hashes remain valid for non-ASCII identifiers.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _hex(name: str, value: object) -> str:
    normalized = _text(name, value).casefold()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


def _strict_keys(name: str, value: object, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} keys do not match schema; missing={missing}, extra={extra}")
    return value


def _checkpoint_payload(checkpoint: DataPlaneRecoveryCheckpoint) -> dict[str, object]:
    if checkpoint.schema != CHECKPOINT_SCHEMA:
        raise ValueError("checkpoint has an incompatible schema")
    if not checkpoint.quiescent_routes_verified:
        raise ValueError("checkpoint must have verified quiescent routes")
    if checkpoint.automatic_control_allowed:
        raise ValueError("recovery interchange cannot authorize automatic control")
    if checkpoint.route_count != len(checkpoint.routes):
        raise ValueError("checkpoint route_count does not match route inventory")

    routes: list[dict[str, object]] = []
    deployment_ids: list[str] = []
    for route in checkpoint.routes:
        deployment_id = _text("deployment_id", route.deployment_id)
        deployment_ids.append(deployment_id)
        generation = route.source_generation
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("source_generation must be a positive integer")
        manifest = None if route.verification_manifest_sha256 is None else _hex(
            "verification_manifest_sha256", route.verification_manifest_sha256
        )
        routes.append(
            {
                "deployment_id": deployment_id,
                "candidate_id": _text("candidate_id", route.candidate_id),
                "artifact_sha256": _hex("artifact_sha256", route.artifact_sha256),
                "verification_manifest_sha256": manifest,
                "source_generation": generation,
            }
        )

    if deployment_ids != sorted(deployment_ids) or len(set(deployment_ids)) != len(deployment_ids):
        raise ValueError("checkpoint route inventory must be sorted and unique")

    p58_content = {"schema": CHECKPOINT_SCHEMA, "routes": routes}
    expected_checkpoint_sha = _sha256(_canonical_json_bytes(p58_content))
    if _hex("checkpoint_sha256", checkpoint.checkpoint_sha256) != expected_checkpoint_sha:
        raise ValueError("checkpoint content does not match checkpoint_sha256")

    return {
        "schema": checkpoint.schema,
        "routes": routes,
        "route_count": checkpoint.route_count,
        "checkpoint_sha256": expected_checkpoint_sha,
        "quiescent_routes_verified": True,
        "automatic_control_allowed": False,
    }


@dataclass(frozen=True)
class RecoveryInterchangeEvidence:
    interchange_schema: str
    checkpoint_sha256: str
    payload_sha256: str
    payload_size_bytes: int
    canonical_roundtrip_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def export_recovery_checkpoint(checkpoint: DataPlaneRecoveryCheckpoint) -> bytes:
    """Export a valid P58 checkpoint as deterministic canonical UTF-8 JSON bytes."""
    return _canonical_json_bytes(
        {"schema": INTERCHANGE_SCHEMA, "checkpoint": _checkpoint_payload(checkpoint), "automatic_control_allowed": False}
    )


def import_recovery_checkpoint(data: bytes) -> tuple[DataPlaneRecoveryCheckpoint, RecoveryInterchangeEvidence]:
    """Strictly parse canonical P59 bytes and reconstruct the exact P58 checkpoint."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("recovery interchange payload must be non-empty bytes")
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("recovery interchange payload must be valid UTF-8") from exc
    try:
        raw = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("recovery interchange payload must be valid JSON") from exc

    envelope = _strict_keys("interchange envelope", raw, {"schema", "checkpoint", "automatic_control_allowed"})
    if envelope["schema"] != INTERCHANGE_SCHEMA:
        raise ValueError("recovery interchange has an incompatible schema")
    if envelope["automatic_control_allowed"] is not False:
        raise ValueError("recovery interchange cannot authorize automatic control")

    cp = _strict_keys(
        "checkpoint",
        envelope["checkpoint"],
        {"schema", "routes", "route_count", "checkpoint_sha256", "quiescent_routes_verified", "automatic_control_allowed"},
    )
    if cp["schema"] != CHECKPOINT_SCHEMA:
        raise ValueError("checkpoint has an incompatible schema")
    if cp["quiescent_routes_verified"] is not True:
        raise ValueError("checkpoint must have verified quiescent routes")
    if cp["automatic_control_allowed"] is not False:
        raise ValueError("checkpoint cannot authorize automatic control")
    route_count = cp["route_count"]
    if isinstance(route_count, bool) or not isinstance(route_count, int) or route_count < 0:
        raise ValueError("route_count must be a non-negative integer")
    if not isinstance(cp["routes"], list) or len(cp["routes"]) != route_count:
        raise ValueError("checkpoint route_count does not match route inventory")

    routes: list[ActiveRouteIdentity] = []
    for index, item in enumerate(cp["routes"]):
        route = _strict_keys(
            f"route[{index}]",
            item,
            {"deployment_id", "candidate_id", "artifact_sha256", "verification_manifest_sha256", "source_generation"},
        )
        generation = route["source_generation"]
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("source_generation must be a positive integer")
        manifest_value = route["verification_manifest_sha256"]
        manifest = None if manifest_value is None else _hex("verification_manifest_sha256", manifest_value)
        routes.append(
            ActiveRouteIdentity(
                deployment_id=_text("deployment_id", route["deployment_id"]),
                candidate_id=_text("candidate_id", route["candidate_id"]),
                artifact_sha256=_hex("artifact_sha256", route["artifact_sha256"]),
                verification_manifest_sha256=manifest,
                source_generation=generation,
            )
        )

    checkpoint = DataPlaneRecoveryCheckpoint(
        schema=CHECKPOINT_SCHEMA,
        routes=tuple(routes),
        route_count=route_count,
        checkpoint_sha256=_hex("checkpoint_sha256", cp["checkpoint_sha256"]),
        quiescent_routes_verified=True,
        automatic_control_allowed=False,
    )
    canonical = export_recovery_checkpoint(checkpoint)
    if canonical != data:
        raise ValueError("recovery interchange payload is not canonical or does not round-trip exactly")

    return checkpoint, RecoveryInterchangeEvidence(
        interchange_schema=INTERCHANGE_SCHEMA,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        payload_sha256=_sha256(data),
        payload_size_bytes=len(data),
        canonical_roundtrip_verified=True,
    )
