from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .process_transfer_fencing_receipt_persistence import load_fenced_restart_evidence_receipt
from .process_transfer_fencing_receipt_restart import _verify_exact_restart_binding
from .process_transfer_restart import ProcessTransferRestartVerification, verify_persisted_process_transfer_restart


EVIDENCE_STATE = "VERIFIED_PROTECTED_RESOURCE_FENCING_TOKEN_CONSUMPTION_NO_CUTOVER_AUTHORITY"
TRUTH_BOUNDARY = (
    "This gate replays the exact persisted fenced-restart receipt and exact local restart evidence before asking a caller-"
    "supplied protected-resource token consumer to validate the receipt's fencing authority and generation for one exact "
    "resource identity. A successful callback is evidence only that the supplied consumer reported acceptance of that token "
    "at that invocation. MORPHEUS does not implement, authenticate, attest, persist, replicate or prove the protected "
    "resource or consumer, does not prove its stale-token rejection semantics, linearizability, durability, availability or "
    "compromise resistance, and cannot prove the token remains accepted after return. This is not an atomic cutover, lease, "
    "lock, consensus protocol, distributed transaction, process activation or traffic switch. Automatic control, activation "
    "and traffic switching remain forbidden. No benchmark, performance, novelty, scientific-effect, HA/SLA or production-"
    "readiness claim is made."
)


@dataclass(frozen=True)
class ProtectedResourceFencingDecision:
    """Caller-supplied protected-resource decision for one exact fencing token.

    The consumer contract is intentionally explicit: a conforming consumer must identify the resource and fencing authority
    it evaluated, echo the exact non-negative fencing generation, and report a real boolean acceptance decision. MORPHEUS
    validates this returned statement but does not attest the implementation behind it.
    """

    resource_id: str
    fencing_authority_id: str
    fencing_counter: int
    accepted: bool


@dataclass(frozen=True)
class ProtectedResourceFencingVerification:
    receipt_sha256: str
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    protected_resource_id: str
    fencing_authority_id: str
    previous_fencing_counter: int
    fencing_counter: int
    receipt_replay_verified: bool = True
    local_restart_evidence_reverified: bool = True
    exact_receipt_local_binding_verified: bool = True
    protected_resource_identity_verified: bool = True
    protected_resource_fencing_token_accepted: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = EVIDENCE_STATE
    truth_boundary: str = TRUTH_BOUNDARY


def _require_nonempty_identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_consumer_decision(
    decision: object,
    *,
    expected_resource_id: str,
    expected_fencing_authority_id: str,
    expected_fencing_counter: int,
) -> ProtectedResourceFencingDecision:
    if not isinstance(decision, ProtectedResourceFencingDecision):
        raise ValueError("protected resource token consumer must return ProtectedResourceFencingDecision")
    if decision.resource_id != expected_resource_id:
        raise ValueError("protected resource token decision resource_id does not match expected identity")
    if decision.fencing_authority_id != expected_fencing_authority_id:
        raise ValueError("protected resource token decision fencing_authority_id does not match receipt identity")
    if (
        not isinstance(decision.fencing_counter, int)
        or isinstance(decision.fencing_counter, bool)
        or decision.fencing_counter < 0
    ):
        raise ValueError("protected resource token decision fencing_counter must be a non-negative integer")
    if decision.fencing_counter != expected_fencing_counter:
        raise ValueError("protected resource token decision fencing_counter does not match receipt generation")
    if not isinstance(decision.accepted, bool):
        raise ValueError("protected resource token decision accepted must be boolean")
    if decision.accepted is not True:
        raise ValueError("protected resource rejected the fenced restart token")
    return decision


def verify_persisted_fenced_restart_protected_resource_token(
    receipt_path: str | os.PathLike[str],
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
    protected_resource_id: str,
    validate_fencing_token: Callable[[str, str, int], ProtectedResourceFencingDecision],
    expected_key_id: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_bundle_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_fencing_authority_id: str,
    expected_previous_fencing_counter: int,
    expected_fencing_counter: int,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProtectedResourceFencingVerification:
    """Validate an exact restart fencing generation at one caller-named protected resource.

    Failure ordering is deliberate. The consumer is not contacted until the persisted receipt has passed exact replay and the
    local restart head/bundle have been reverified and bound to that receipt. The consumer must then report acceptance for the
    exact resource identity, fencing authority and generation. This function validates evidence only; it never activates or
    switches the protected resource.
    """

    protected_resource_id = _require_nonempty_identity(protected_resource_id, "protected_resource_id")
    if not callable(validate_fencing_token):
        raise ValueError("validate_fencing_token must be callable")

    receipt = load_fenced_restart_evidence_receipt(
        receipt_path,
        expected_key_id=expected_key_id,
        expected_authority_id=expected_authority_id,
        expected_sequence=expected_sequence,
        expected_head_sha256=expected_head_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
        expected_migration_id=expected_migration_id,
        expected_session_id=expected_session_id,
        expected_target_candidate_id=expected_target_candidate_id,
        expected_fencing_authority_id=expected_fencing_authority_id,
        expected_previous_fencing_counter=expected_previous_fencing_counter,
        expected_fencing_counter=expected_fencing_counter,
    )

    restart: ProcessTransferRestartVerification = verify_persisted_process_transfer_restart(
        head_path,
        bundle_path,
        expected_authority_id=receipt.authority_id,
        expected_sequence=receipt.sequence,
        expected_head_sha256=receipt.head_sha256,
        expected_migration_id=receipt.migration_id,
        expected_session_id=receipt.session_id,
        expected_target_candidate_id=receipt.target_candidate_id,
        expected_schema_identity=expected_schema_identity,
        expected_codec_identity=expected_codec_identity,
        expected_target_artifact_sha256=expected_target_artifact_sha256,
        expected_verification_manifest_sha256=expected_verification_manifest_sha256,
    )
    _verify_exact_restart_binding(restart, receipt)

    try:
        decision = validate_fencing_token(
            protected_resource_id,
            receipt.fencing_authority_id,
            receipt.fencing_counter,
        )
    except Exception as exc:
        raise ValueError("protected resource fencing-token validation failed") from exc

    _validate_consumer_decision(
        decision,
        expected_resource_id=protected_resource_id,
        expected_fencing_authority_id=receipt.fencing_authority_id,
        expected_fencing_counter=receipt.fencing_counter,
    )

    return ProtectedResourceFencingVerification(
        receipt_sha256=receipt.receipt_sha256,
        key_id=receipt.key_id,
        authority_id=receipt.authority_id,
        sequence=receipt.sequence,
        head_sha256=receipt.head_sha256,
        bundle_sha256=receipt.bundle_sha256,
        migration_id=receipt.migration_id,
        session_id=receipt.session_id,
        target_candidate_id=receipt.target_candidate_id,
        protected_resource_id=protected_resource_id,
        fencing_authority_id=receipt.fencing_authority_id,
        previous_fencing_counter=receipt.previous_fencing_counter,
        fencing_counter=receipt.fencing_counter,
    )
