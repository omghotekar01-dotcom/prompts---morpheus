"""Bind P62 recovery evidence to explicit fresh-bootstrap generation semantics.

P63 closes a narrow ambiguity left by P58-P62: P58 preserves each source route's
active generation as provenance, while P60/P62 intentionally verify route identity
without claiming generation-number continuity across restart. A freshly bootstrapped
VersionedArtifactRouter starts active routes at generation 1. This gate proves that
the exact P61/P62-bound checkpoint preserves the source-generation inventory while
the supplied recovered quiescent router follows that explicit reset-to-1 policy.

Generation numbers are local router metadata, not durable logical clocks. This gate
therefore does not turn them into cross-process ordering or distributed epochs.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from .dataplane import VersionedArtifactRouter
from .dataplane_recovery_interchange import import_recovery_checkpoint
from .dataplane_recovery_store import RecoveryStoreEvidence, load_recovery_payload
from .dataplane_recovery_store_rebootstrap import (
    EVIDENCE_STATE as P62_EVIDENCE_STATE,
    RecoveryStoreRebootstrapEvidence,
    verify_rebootstrap_from_store,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_GENERATION_SEMANTICS_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact P61/P62-bound checkpoint retains each source route generation as provenance "
    "and that the supplied quiescent recovered in-process router uses VersionedArtifactRouter fresh-bootstrap generation "
    "1 for every recovered active route. It explicitly does not prove generation-number continuity across restart, a "
    "durable logical clock, distributed ordering, native-object restoration, staged/rollback history restoration, reader-" 
    "lease recovery, crash consistency, HA, cross-process hot swap, production readiness or performance."
)


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_generation(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class RecoveryGenerationEvidence:
    checkpoint_sha256: str
    payload_sha256: str
    route_count: int
    source_generations_sha256: str
    recovered_generations_sha256: str
    generation_binding_sha256: str
    source_generation_provenance_verified: bool
    fresh_bootstrap_generation_verified: bool
    p62_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_generation_semantics(
    path: str | os.PathLike[str],
    recovered_router: VersionedArtifactRouter,
    store_evidence: RecoveryStoreEvidence,
    store_rebootstrap_evidence: RecoveryStoreRebootstrapEvidence,
) -> RecoveryGenerationEvidence:
    """Verify source-generation provenance plus explicit fresh-bootstrap reset semantics."""
    if store_rebootstrap_evidence.evidence_state != P62_EVIDENCE_STATE:
        raise ValueError("P62 rebootstrap evidence has an incompatible evidence state")
    if not store_rebootstrap_evidence.stored_payload_identity_verified:
        raise ValueError("P62 rebootstrap evidence is not stored-payload verified")
    if not store_rebootstrap_evidence.canonical_interchange_verified:
        raise ValueError("P62 rebootstrap evidence is not canonical-interchange verified")
    if not store_rebootstrap_evidence.restart_route_consistency_verified:
        raise ValueError("P62 rebootstrap evidence is not restart-route verified")
    if not store_rebootstrap_evidence.store_rebootstrap_consistency_verified:
        raise ValueError("P62 rebootstrap evidence is not store-rebootstrap verified")
    if store_rebootstrap_evidence.automatic_control_allowed:
        raise ValueError("P62 rebootstrap evidence cannot authorize automatic control")

    recomputed_p62 = verify_rebootstrap_from_store(path, recovered_router, store_evidence)
    if recomputed_p62 != store_rebootstrap_evidence:
        raise ValueError("supplied P62 evidence does not match exact store/router recomputation")

    payload = load_recovery_payload(path, expected_payload_sha256=store_rebootstrap_evidence.payload_sha256)
    if len(payload) != store_rebootstrap_evidence.payload_size_bytes:
        raise ValueError("P62 payload-size drift")
    checkpoint, interchange = import_recovery_checkpoint(payload)
    if checkpoint.checkpoint_sha256 != store_rebootstrap_evidence.checkpoint_sha256:
        raise ValueError("checkpoint identity drift from P62")
    if interchange.payload_sha256 != store_rebootstrap_evidence.payload_sha256:
        raise ValueError("payload identity drift from P62")
    if checkpoint.route_count != store_rebootstrap_evidence.route_count:
        raise ValueError("route-count drift from P62")

    recovered = recovered_router.list()
    if len(recovered) != checkpoint.route_count:
        raise ValueError("recovered router deployment count does not match checkpoint")
    recovered_by_id: dict[str, dict[str, Any]] = {}
    for deployment in recovered:
        deployment_id = deployment.get("deployment_id")
        if not isinstance(deployment_id, str) or not deployment_id.strip():
            raise ValueError("recovered deployment_id must be a non-empty string")
        deployment_id = deployment_id.strip()
        if deployment_id in recovered_by_id:
            raise ValueError("recovered router contains duplicate deployment identifiers")
        recovered_by_id[deployment_id] = deployment

    source_generations: list[dict[str, object]] = []
    recovered_generations: list[dict[str, object]] = []
    for route in checkpoint.routes:
        source_generation = _positive_generation("source_generation", route.source_generation)
        deployment = recovered_by_id.get(route.deployment_id)
        if deployment is None:
            raise ValueError(f"recovered router is missing deployment {route.deployment_id}")
        active = deployment.get("active")
        if not isinstance(active, dict):
            raise ValueError(f"recovered deployment {route.deployment_id} is missing active route state")
        recovered_generation = _positive_generation("recovered generation", active.get("generation"))
        if recovered_generation != 1:
            raise ValueError(
                f"recovered deployment {route.deployment_id} does not follow fresh-bootstrap generation reset policy"
            )
        source_generations.append(
            {"deployment_id": route.deployment_id, "source_generation": source_generation}
        )
        recovered_generations.append(
            {"deployment_id": route.deployment_id, "recovered_generation": recovered_generation}
        )

    source_sha = _canonical_sha(source_generations)
    recovered_sha = _canonical_sha(recovered_generations)
    binding_payload = {
        "checkpoint_sha256": checkpoint.checkpoint_sha256,
        "payload_sha256": interchange.payload_sha256,
        "route_count": checkpoint.route_count,
        "source_generations_sha256": source_sha,
        "recovered_generations_sha256": recovered_sha,
        "p62_binding_sha256": store_rebootstrap_evidence.binding_sha256,
        "p62_evidence_state": store_rebootstrap_evidence.evidence_state,
        "generation_policy": "fresh_bootstrap_resets_active_generation_to_1",
    }
    return RecoveryGenerationEvidence(
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        payload_sha256=interchange.payload_sha256,
        route_count=checkpoint.route_count,
        source_generations_sha256=source_sha,
        recovered_generations_sha256=recovered_sha,
        generation_binding_sha256=_canonical_sha(binding_payload),
        source_generation_provenance_verified=True,
        fresh_bootstrap_generation_verified=True,
        p62_evidence_state=store_rebootstrap_evidence.evidence_state,
    )
