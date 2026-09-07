from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from .process_transfer_fencing_receipt_persistence import load_fenced_restart_evidence_receipt
from .process_transfer_restart import ProcessTransferRestartVerification, verify_persisted_process_transfer_restart


EVIDENCE_STATE = "VERIFIED_FENCED_RECEIPT_RESTART_CURRENTNESS_NO_CUTOVER_AUTHORITY"
TRUTH_BOUNDARY = (
    "This gate replays an exact persisted fenced-restart receipt, asks a caller-supplied read-only fencing-counter resolver "
    "for the named authority's currently observed counter, requires that observation to equal the receipt's already-claimed "
    "counter, and then re-verifies the exact local head and evidence bundle named by the receipt. The external counter read "
    "is an observation supplied by the caller, not a MORPHEUS-attested clock, lease, consensus service or atomic snapshot; "
    "the counter can change immediately before or after the callback. MORPHEUS does not implement, authenticate, persist, "
    "replicate or prove correctness/linearizability/durability/availability of that authority, does not atomically bind the "
    "external read to local filesystem verification, does not perform another compare-and-advance, does not guarantee "
    "rollback resistance under an adversarial store, and does not authorize activation, automatic control or traffic "
    "switching. No benchmark, performance, novelty, scientific-effect, HA/SLA or production-readiness claim is made."
)

BRACKETED_EVIDENCE_STATE = "VERIFIED_FENCED_RECEIPT_RESTART_BRACKETED_CURRENTNESS_NO_CUTOVER_AUTHORITY"
BRACKETED_TRUTH_BOUNDARY = (
    "This gate strengthens the read-only restart-currentness check by requiring the exact receipt fencing counter to be "
    "observed both immediately before and immediately after exact local head/bundle replay. Equality of two caller-supplied "
    "observations narrows one local TOCTOU window but is not an atomic snapshot, lease, lock, compare-and-advance, consensus "
    "operation or proof that the generation remained unchanged between reads. MORPHEUS does not implement or attest the "
    "external fencing authority, cannot prevent a counter change after the second observation, and grants no activation, "
    "automatic-control or traffic-switching authority. No performance, novelty, scientific-effect, HA/SLA or production-"
    "readiness claim is made."
)


@dataclass(frozen=True)
class FencedRestartCurrentnessVerification:
    receipt_sha256: str
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    fencing_authority_id: str
    previous_fencing_counter: int
    fencing_counter: int
    observed_fencing_counter: int
    receipt_replay_verified: bool = True
    external_counter_observation_verified: bool = True
    local_restart_evidence_reverified: bool = True
    exact_receipt_local_binding_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = EVIDENCE_STATE
    truth_boundary: str = TRUTH_BOUNDARY


@dataclass(frozen=True)
class BracketedFencedRestartCurrentnessVerification:
    receipt_sha256: str
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    fencing_authority_id: str
    previous_fencing_counter: int
    fencing_counter: int
    observed_fencing_counter_before: int
    observed_fencing_counter_after: int
    receipt_replay_verified: bool = True
    pre_replay_counter_observation_verified: bool = True
    local_restart_evidence_reverified: bool = True
    exact_receipt_local_binding_verified: bool = True
    post_replay_counter_observation_verified: bool = True
    bracketed_counter_equality_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = BRACKETED_EVIDENCE_STATE
    truth_boundary: str = BRACKETED_TRUTH_BOUNDARY


def _require_counter(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _read_external_counter(read_fencing_counter: Callable[[str], int], authority_id: str, field: str) -> int:
    try:
        observed = read_fencing_counter(authority_id)
    except Exception as exc:
        raise ValueError("external fencing authority current-counter observation failed") from exc
    return _require_counter(observed, field)


def _verify_exact_restart_binding(restart: ProcessTransferRestartVerification, receipt: Any) -> None:
    exact_pairs = (
        ("authority_id", restart.authority_id, receipt.authority_id),
        ("sequence", restart.sequence, receipt.sequence),
        ("head_sha256", restart.head_sha256, receipt.head_sha256),
        ("bundle_sha256", restart.bundle_sha256, receipt.bundle_sha256),
        ("migration_id", restart.migration_id, receipt.migration_id),
        ("session_id", restart.session_id, receipt.session_id),
        ("target_candidate_id", restart.target_candidate_id, receipt.target_candidate_id),
    )
    for field, actual, expected in exact_pairs:
        if actual != expected:
            raise ValueError(f"restart {field} does not match persisted fenced receipt identity")


def verify_persisted_fenced_restart_currentness(
    receipt_path: str | os.PathLike[str],
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
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
    read_fencing_counter: Callable[[str], int],
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> FencedRestartCurrentnessVerification:
    """Re-establish receipt/local consistency and conditionally reject a superseded fencing generation.

    The caller-supplied resolver is deliberately read-only. This function never claims or rolls back a fencing generation.
    Receipt replay happens before the external observation so malformed/unexpected persisted evidence cannot trigger external
    resolver access. The local head/bundle replay follows the observation and must still bind the exact receipt identities.
    """

    if not callable(read_fencing_counter):
        raise ValueError("read_fencing_counter must be callable")

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

    observed_fencing_counter = _read_external_counter(
        read_fencing_counter, receipt.fencing_authority_id, "observed_fencing_counter"
    )
    if observed_fencing_counter != receipt.fencing_counter:
        raise ValueError("persisted fenced restart receipt is not current at the supplied fencing authority observation")

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

    return FencedRestartCurrentnessVerification(
        receipt_sha256=receipt.receipt_sha256,
        key_id=receipt.key_id,
        authority_id=receipt.authority_id,
        sequence=receipt.sequence,
        head_sha256=receipt.head_sha256,
        bundle_sha256=receipt.bundle_sha256,
        migration_id=receipt.migration_id,
        session_id=receipt.session_id,
        target_candidate_id=receipt.target_candidate_id,
        fencing_authority_id=receipt.fencing_authority_id,
        previous_fencing_counter=receipt.previous_fencing_counter,
        fencing_counter=receipt.fencing_counter,
        observed_fencing_counter=observed_fencing_counter,
    )


def verify_persisted_fenced_restart_bracketed_currentness(
    receipt_path: str | os.PathLike[str],
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
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
    read_fencing_counter: Callable[[str], int],
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> BracketedFencedRestartCurrentnessVerification:
    """Bracket exact local restart replay with two matching read-only fencing observations.

    This is intentionally weaker than an atomic lease/fence protocol. A successful result proves only that both resolver calls
    returned the receipt's exact fencing generation around the tested local replay; it does not prove the counter stayed fixed
    between calls or after return.
    """

    if not callable(read_fencing_counter):
        raise ValueError("read_fencing_counter must be callable")

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

    observed_before = _read_external_counter(
        read_fencing_counter, receipt.fencing_authority_id, "observed_fencing_counter_before"
    )
    if observed_before != receipt.fencing_counter:
        raise ValueError("persisted fenced restart receipt is not current at the pre-replay fencing authority observation")

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

    observed_after = _read_external_counter(
        read_fencing_counter, receipt.fencing_authority_id, "observed_fencing_counter_after"
    )
    if observed_after != receipt.fencing_counter:
        raise ValueError("persisted fenced restart receipt was superseded by the post-replay fencing authority observation")
    if observed_before != observed_after:
        raise ValueError("bracketed fencing authority observations do not match")

    return BracketedFencedRestartCurrentnessVerification(
        receipt_sha256=receipt.receipt_sha256,
        key_id=receipt.key_id,
        authority_id=receipt.authority_id,
        sequence=receipt.sequence,
        head_sha256=receipt.head_sha256,
        bundle_sha256=receipt.bundle_sha256,
        migration_id=receipt.migration_id,
        session_id=receipt.session_id,
        target_candidate_id=receipt.target_candidate_id,
        fencing_authority_id=receipt.fencing_authority_id,
        previous_fencing_counter=receipt.previous_fencing_counter,
        fencing_counter=receipt.fencing_counter,
        observed_fencing_counter_before=observed_before,
        observed_fencing_counter_after=observed_after,
    )
