"""Bind P61 local-store evidence to P60 recovered-router verification.

P62 closes the local restart seam between publication and rebootstrap: the exact
bytes currently present at a caller-selected P61 store path must still match the
P61 publication evidence, then those same bytes must pass P60 verification against
the supplied recovered in-process router. This is an integrity-composition gate;
it does not expand MORPHEUS into durable/distributed persistence or native-object
recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from .dataplane import VersionedArtifactRouter
from .dataplane_recovery_rebootstrap import EVIDENCE_STATE as P60_EVIDENCE_STATE
from .dataplane_recovery_rebootstrap import verify_rebootstrap_from_interchange
from .dataplane_recovery_store import EVIDENCE_STATE as P61_EVIDENCE_STATE
from .dataplane_recovery_store import RecoveryStoreEvidence, load_recovery_payload

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STORE_REBOOTSTRAP_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact bytes read from one caller-selected P61 local store path still match the "
    "supplied P61 publication evidence and that those same canonical bytes verify under P60 against the supplied "
    "quiescent recovered in-process router. It does not prove power-loss crash consistency, directory-entry or hardware "
    "durability, replication, HA, distributed coordination, native-object restoration, staged-migration or rollback "
    "recovery, reader-lease recovery, cross-process hot swap, production readiness or performance."
)


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RecoveryStoreRebootstrapEvidence:
    checkpoint_sha256: str
    payload_sha256: str
    payload_size_bytes: int
    route_count: int
    recovered_routes_sha256: str
    binding_sha256: str
    stored_payload_identity_verified: bool
    canonical_interchange_verified: bool
    restart_route_consistency_verified: bool
    store_rebootstrap_consistency_verified: bool
    p61_evidence_state: str
    p60_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_rebootstrap_from_store(
    path: str | os.PathLike[str],
    recovered_router: VersionedArtifactRouter,
    store_evidence: RecoveryStoreEvidence,
) -> RecoveryStoreRebootstrapEvidence:
    """Verify exact P61-stored bytes through the P60 recovered-router binding."""
    if store_evidence.evidence_state != P61_EVIDENCE_STATE:
        raise ValueError("P61 store evidence has an incompatible evidence state")
    if not store_evidence.canonical_interchange_verified:
        raise ValueError("P61 store evidence is not canonical-interchange verified")
    if not store_evidence.same_directory_replace_used:
        raise ValueError("P61 store evidence does not record same-directory replacement")
    if not store_evidence.readback_identity_verified or not store_evidence.store_consistency_verified:
        raise ValueError("P61 store evidence is not store-consistency verified")
    if store_evidence.automatic_control_allowed:
        raise ValueError("P61 store evidence cannot authorize automatic control")

    payload = load_recovery_payload(path, expected_payload_sha256=store_evidence.payload_sha256)
    if len(payload) != store_evidence.payload_size_bytes:
        raise ValueError("P61 store evidence payload-size drift")

    rebootstrap = verify_rebootstrap_from_interchange(payload, recovered_router)
    if rebootstrap.evidence_state != P60_EVIDENCE_STATE:
        raise ValueError("P60 rebootstrap evidence has an incompatible evidence state")
    if not rebootstrap.canonical_interchange_verified:
        raise ValueError("P60 rebootstrap evidence is not canonical-interchange verified")
    if not rebootstrap.restart_route_consistency_verified or not rebootstrap.rebootstrap_binding_verified:
        raise ValueError("P60 rebootstrap evidence is not binding verified")
    if rebootstrap.automatic_control_allowed:
        raise ValueError("P60 rebootstrap evidence cannot authorize automatic control")
    if rebootstrap.checkpoint_sha256 != store_evidence.checkpoint_sha256:
        raise ValueError("P60/P61 checkpoint identity drift")
    if rebootstrap.payload_sha256 != store_evidence.payload_sha256:
        raise ValueError("P60/P61 payload identity drift")
    if rebootstrap.payload_size_bytes != store_evidence.payload_size_bytes:
        raise ValueError("P60/P61 payload-size drift")

    binding_payload = {
        "checkpoint_sha256": rebootstrap.checkpoint_sha256,
        "payload_sha256": rebootstrap.payload_sha256,
        "payload_size_bytes": rebootstrap.payload_size_bytes,
        "route_count": rebootstrap.route_count,
        "recovered_routes_sha256": rebootstrap.recovered_routes_sha256,
        "p61_evidence_state": store_evidence.evidence_state,
        "p60_evidence_state": rebootstrap.evidence_state,
    }
    return RecoveryStoreRebootstrapEvidence(
        checkpoint_sha256=rebootstrap.checkpoint_sha256,
        payload_sha256=rebootstrap.payload_sha256,
        payload_size_bytes=rebootstrap.payload_size_bytes,
        route_count=rebootstrap.route_count,
        recovered_routes_sha256=rebootstrap.recovered_routes_sha256,
        binding_sha256=_canonical_sha(binding_payload),
        stored_payload_identity_verified=True,
        canonical_interchange_verified=True,
        restart_route_consistency_verified=True,
        store_rebootstrap_consistency_verified=True,
        p61_evidence_state=store_evidence.evidence_state,
        p60_evidence_state=rebootstrap.evidence_state,
    )
