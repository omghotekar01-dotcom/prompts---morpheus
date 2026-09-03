"""Deterministic restart-recovery evidence for MORPHEUS local data-plane routing.

P58 closes a narrow startup-grade continuity gap in the existing in-process
VersionedArtifactRouter. It captures only quiescent active-route identities and
later verifies that a freshly bootstrapped router exposes the same deployment,
candidate, artifact and verification-manifest identities.

This module deliberately does not serialize native objects, staged migrations,
rollback stacks, reader leases or controller state. A checkpoint therefore cannot
be described as HA persistence, a distributed transaction, native-object migration
or cross-process hot swap.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .dataplane import VersionedArtifactRouter

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RESTART_RECOVERY_CONSISTENCY_VERIFIED"
CHECKPOINT_SCHEMA = "morpheus.dataplane-active-route-checkpoint/v1"
TRUTH_BOUNDARY = (
    "This gate proves only deterministic identity continuity for quiescent active routes across a caller-managed "
    "restart/rebootstrap boundary. It does not persist or restore native data-structure contents, staged versions, "
    "rollback history, reader leases, runtime sessions or migration-controller state, and it does not establish HA, "
    "crash-consistent storage, distributed atomicity, native cross-process hot swap, production readiness or performance."
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _hex(name: str, value: object) -> str:
    normalized = _text(name, value).casefold()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ActiveRouteIdentity:
    deployment_id: str
    candidate_id: str
    artifact_sha256: str
    verification_manifest_sha256: str | None
    source_generation: int

    def as_dict(self) -> dict[str, object]:
        return {
            "deployment_id": self.deployment_id,
            "candidate_id": self.candidate_id,
            "artifact_sha256": self.artifact_sha256,
            "verification_manifest_sha256": self.verification_manifest_sha256,
            "source_generation": self.source_generation,
        }


@dataclass(frozen=True)
class DataPlaneRecoveryCheckpoint:
    schema: str
    routes: tuple[ActiveRouteIdentity, ...]
    route_count: int
    checkpoint_sha256: str
    quiescent_routes_verified: bool
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "routes": [route.as_dict() for route in self.routes],
            "route_count": self.route_count,
            "checkpoint_sha256": self.checkpoint_sha256,
            "quiescent_routes_verified": self.quiescent_routes_verified,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


@dataclass(frozen=True)
class DataPlaneRecoveryVerification:
    checkpoint_sha256: str
    route_count: int
    recovered_routes_sha256: str
    restart_route_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def capture_active_route_checkpoint(router: VersionedArtifactRouter) -> DataPlaneRecoveryCheckpoint:
    """Capture deterministic active-route identities only from a quiescent router."""

    snapshots = router.list()
    routes: list[ActiveRouteIdentity] = []
    for deployment in snapshots:
        deployment_id = _text("deployment_id", deployment.get("deployment_id"))
        if deployment.get("staged") is not None:
            raise ValueError(f"deployment {deployment_id} has a staged version; checkpoint requires quiescence")
        if int(deployment.get("rollback_depth", 0)) != 0:
            raise ValueError(f"deployment {deployment_id} has rollback history; active-route checkpoint would be lossy")
        active = deployment.get("active")
        if not isinstance(active, dict):
            raise ValueError(f"deployment {deployment_id} is missing active route state")
        generation = active.get("generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("active generation must be a positive integer")
        manifest_value = active.get("verification_manifest_sha256")
        manifest = None if manifest_value is None else _hex("verification_manifest_sha256", manifest_value)
        routes.append(
            ActiveRouteIdentity(
                deployment_id=deployment_id,
                candidate_id=_text("candidate_id", active.get("candidate_id")),
                artifact_sha256=_hex("artifact_sha256", active.get("artifact_sha256")),
                verification_manifest_sha256=manifest,
                source_generation=generation,
            )
        )

    routes.sort(key=lambda route: route.deployment_id)
    if len({route.deployment_id for route in routes}) != len(routes):
        raise ValueError("deployment identifiers must be unique")
    payload = {"schema": CHECKPOINT_SCHEMA, "routes": [route.as_dict() for route in routes]}
    return DataPlaneRecoveryCheckpoint(
        schema=CHECKPOINT_SCHEMA,
        routes=tuple(routes),
        route_count=len(routes),
        checkpoint_sha256=_canonical_sha(payload),
        quiescent_routes_verified=True,
    )


def verify_recovered_active_routes(
    checkpoint: DataPlaneRecoveryCheckpoint,
    recovered_router: VersionedArtifactRouter,
) -> DataPlaneRecoveryVerification:
    """Verify exact active-route identity continuity after caller-managed rebootstrap."""

    if checkpoint.schema != CHECKPOINT_SCHEMA:
        raise ValueError("checkpoint has an incompatible schema")
    if not checkpoint.quiescent_routes_verified:
        raise ValueError("checkpoint must have verified quiescent routes")
    if checkpoint.automatic_control_allowed:
        raise ValueError("recovery evidence cannot authorize automatic control")
    if checkpoint.route_count != len(checkpoint.routes):
        raise ValueError("checkpoint route_count does not match route inventory")

    expected_payload = {"schema": checkpoint.schema, "routes": [route.as_dict() for route in checkpoint.routes]}
    if _hex("checkpoint_sha256", checkpoint.checkpoint_sha256) != _canonical_sha(expected_payload):
        raise ValueError("checkpoint content does not match checkpoint_sha256")

    expected_ids = [route.deployment_id for route in checkpoint.routes]
    if expected_ids != sorted(expected_ids) or len(set(expected_ids)) != len(expected_ids):
        raise ValueError("checkpoint route inventory must be sorted and unique")

    recovered = recovered_router.list()
    if len(recovered) != checkpoint.route_count:
        raise ValueError("recovered router deployment count does not match checkpoint")
    recovered_by_id: dict[str, dict[str, Any]] = {}
    for deployment in recovered:
        deployment_id = _text("recovered deployment_id", deployment.get("deployment_id"))
        if deployment_id in recovered_by_id:
            raise ValueError("recovered router contains duplicate deployment identifiers")
        if deployment.get("staged") is not None:
            raise ValueError(f"recovered deployment {deployment_id} unexpectedly has a staged version")
        if int(deployment.get("rollback_depth", 0)) != 0:
            raise ValueError(f"recovered deployment {deployment_id} unexpectedly has rollback history")
        recovered_by_id[deployment_id] = deployment

    recovered_payload: list[dict[str, object]] = []
    for expected in checkpoint.routes:
        deployment = recovered_by_id.get(expected.deployment_id)
        if deployment is None:
            raise ValueError(f"recovered router is missing deployment {expected.deployment_id}")
        active = deployment.get("active")
        if not isinstance(active, dict):
            raise ValueError(f"recovered deployment {expected.deployment_id} is missing active route state")
        candidate_id = _text("recovered candidate_id", active.get("candidate_id"))
        artifact_sha256 = _hex("recovered artifact_sha256", active.get("artifact_sha256"))
        manifest_value = active.get("verification_manifest_sha256")
        manifest = None if manifest_value is None else _hex("recovered verification_manifest_sha256", manifest_value)
        if candidate_id != expected.candidate_id:
            raise ValueError(f"recovered candidate identity drift for deployment {expected.deployment_id}")
        if artifact_sha256 != expected.artifact_sha256:
            raise ValueError(f"recovered artifact identity drift for deployment {expected.deployment_id}")
        if manifest != expected.verification_manifest_sha256:
            raise ValueError(f"recovered verification-manifest identity drift for deployment {expected.deployment_id}")
        recovered_payload.append(
            {
                "deployment_id": expected.deployment_id,
                "candidate_id": candidate_id,
                "artifact_sha256": artifact_sha256,
                "verification_manifest_sha256": manifest,
            }
        )

    return DataPlaneRecoveryVerification(
        checkpoint_sha256=checkpoint.checkpoint_sha256.casefold(),
        route_count=checkpoint.route_count,
        recovered_routes_sha256=_canonical_sha(recovered_payload),
        restart_route_consistency_verified=True,
    )
