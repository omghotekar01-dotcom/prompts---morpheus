"""Bind canonical P59 recovery bytes to a verified P58 rebootstrap state.

P60 closes the seam between byte interchange and restart verification: the exact
canonical bytes are parsed into a P58 checkpoint and that reconstructed checkpoint
is then verified against the supplied recovered in-process router. This is an
evidence-composition gate only; it does not perform persistence or rebootstrap.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane import VersionedArtifactRouter
from .dataplane_recovery import EVIDENCE_STATE as P58_EVIDENCE_STATE
from .dataplane_recovery import verify_recovered_active_routes
from .dataplane_recovery_interchange import EVIDENCE_STATE as P59_EVIDENCE_STATE
from .dataplane_recovery_interchange import import_recovery_checkpoint

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_REBOOTSTRAP_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact canonical P59 payload was parsed into a valid P58 checkpoint and that the "
    "checkpoint's quiescent active-route identities match the supplied recovered in-process router under P58. It does "
    "not prove durable storage, crash consistency, native-object restoration, staged-migration or rollback recovery, "
    "reader-lease recovery, distributed coordination, cross-process hot swap, production readiness or performance."
)


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RecoveryRebootstrapBindingEvidence:
    checkpoint_sha256: str
    payload_sha256: str
    payload_size_bytes: int
    route_count: int
    recovered_routes_sha256: str
    binding_sha256: str
    canonical_interchange_verified: bool
    restart_route_consistency_verified: bool
    rebootstrap_binding_verified: bool
    p59_evidence_state: str
    p58_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_rebootstrap_from_interchange(
    payload: bytes,
    recovered_router: VersionedArtifactRouter,
) -> RecoveryRebootstrapBindingEvidence:
    """Verify one exact P59 payload all the way through the P58 recovered router."""

    checkpoint, interchange = import_recovery_checkpoint(payload)
    if interchange.evidence_state != P59_EVIDENCE_STATE:
        raise ValueError("P59 interchange evidence has an incompatible evidence state")
    if not interchange.canonical_roundtrip_verified:
        raise ValueError("P59 interchange evidence is not canonically verified")
    if interchange.automatic_control_allowed:
        raise ValueError("P59 interchange evidence cannot authorize automatic control")
    if interchange.checkpoint_sha256 != checkpoint.checkpoint_sha256:
        raise ValueError("P59 interchange evidence checkpoint identity drift")

    recovery = verify_recovered_active_routes(checkpoint, recovered_router)
    if recovery.evidence_state != P58_EVIDENCE_STATE:
        raise ValueError("P58 recovery evidence has an incompatible evidence state")
    if not recovery.restart_route_consistency_verified:
        raise ValueError("P58 recovery evidence is not restart-consistency verified")
    if recovery.automatic_control_allowed:
        raise ValueError("P58 recovery evidence cannot authorize automatic control")
    if recovery.checkpoint_sha256 != checkpoint.checkpoint_sha256:
        raise ValueError("P58 recovery evidence checkpoint identity drift")
    if recovery.route_count != checkpoint.route_count:
        raise ValueError("P58 recovery evidence route-count drift")

    binding_payload = {
        "checkpoint_sha256": checkpoint.checkpoint_sha256,
        "payload_sha256": interchange.payload_sha256,
        "payload_size_bytes": interchange.payload_size_bytes,
        "route_count": checkpoint.route_count,
        "recovered_routes_sha256": recovery.recovered_routes_sha256,
        "p59_evidence_state": interchange.evidence_state,
        "p58_evidence_state": recovery.evidence_state,
    }
    return RecoveryRebootstrapBindingEvidence(
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        payload_sha256=interchange.payload_sha256,
        payload_size_bytes=interchange.payload_size_bytes,
        route_count=checkpoint.route_count,
        recovered_routes_sha256=recovery.recovered_routes_sha256,
        binding_sha256=_canonical_sha(binding_payload),
        canonical_interchange_verified=True,
        restart_route_consistency_verified=True,
        rebootstrap_binding_verified=True,
        p59_evidence_state=interchange.evidence_state,
        p58_evidence_state=recovery.evidence_state,
    )
