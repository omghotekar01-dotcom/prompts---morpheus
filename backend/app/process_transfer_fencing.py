from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from .process_transfer_restart import ProcessTransferRestartVerification, verify_persisted_process_transfer_restart


FENCED_AUTHENTICATED_RESTART_STATE = (
    "VERIFIED_EXTERNALLY_FENCED_AUTHENTICATED_LOCAL_PROCESS_TRANSFER_RESTART_EVIDENCE_NO_ACTIVATION"
)
FENCING_AUTHENTICATION_VERSION = "morpheus-process-transfer-restart-fencing-auth-v1"
FENCING_TRUTH_BOUNDARY = (
    "This gate authenticates an exact local restart expectation together with a caller-named external fencing authority, "
    "an exact expected current fencing counter and the immediately next requested fencing counter. It then asks one "
    "caller-supplied compare-and-advance operation to claim that next counter before replaying the existing exact local "
    "restart evidence verification. MORPHEUS verifies only the callback contract and returned counter; it does not "
    "implement, authenticate, persist, replicate, attest or prove atomicity, linearizability, durability, availability, "
    "compromise resistance or multi-receiver correctness of the external fencing authority. A claimed fencing counter is "
    "evidence of the caller-supplied authority response, not activation, automatic-control, traffic-switching, lease or "
    "production authority. Failed local replay after an external claim does not roll the external counter back. No "
    "performance, novelty, scientific-effect, HA/SLA or production-readiness claim is made."
)


@dataclass(frozen=True)
class FencedAuthenticatedProcessTransferRestartVerification:
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
    authentication_verified: bool = True
    external_fencing_claim_verified: bool = True
    restart_evidence_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = FENCED_AUTHENTICATED_RESTART_STATE
    truth_boundary: str = FENCING_TRUTH_BOUNDARY


def _require_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a non-empty single-line string")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _require_counter(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _require_authentication_key(value: Any) -> bytes:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ValueError("authentication_key must be at least 32 bytes")
    return value


def _fencing_authentication_statement(
    *,
    key_id: str,
    authority_id: str,
    sequence: int,
    head_sha256: str,
    fencing_authority_id: str,
    previous_fencing_counter: int,
    fencing_counter: int,
) -> bytes:
    key_id = _require_identity(key_id, "key_id")
    authority_id = _require_identity(authority_id, "authority_id")
    head_sha256 = _require_sha256(head_sha256, "head_sha256")
    fencing_authority_id = _require_identity(fencing_authority_id, "fencing_authority_id")
    previous_fencing_counter = _require_counter(previous_fencing_counter, "previous_fencing_counter")
    fencing_counter = _require_counter(fencing_counter, "fencing_counter")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    if fencing_counter != previous_fencing_counter + 1:
        raise ValueError("fencing_counter must be exactly previous_fencing_counter + 1")
    payload = {
        "authority_id": authority_id,
        "fencing_authority_id": fencing_authority_id,
        "fencing_counter": fencing_counter,
        "head_sha256": head_sha256,
        "key_id": key_id,
        "previous_fencing_counter": previous_fencing_counter,
        "sequence": sequence,
        "version": FENCING_AUTHENTICATION_VERSION,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def create_fenced_process_transfer_restart_authentication_tag(
    *,
    authentication_key: bytes,
    key_id: str,
    authority_id: str,
    sequence: int,
    head_sha256: str,
    fencing_authority_id: str,
    previous_fencing_counter: int,
    fencing_counter: int,
) -> str:
    """Authenticate one exact external compare-and-advance request plus the local restart head expectation."""

    key = _require_authentication_key(authentication_key)
    statement = _fencing_authentication_statement(
        key_id=key_id,
        authority_id=authority_id,
        sequence=sequence,
        head_sha256=head_sha256,
        fencing_authority_id=fencing_authority_id,
        previous_fencing_counter=previous_fencing_counter,
        fencing_counter=fencing_counter,
    )
    return hmac.new(key, statement, hashlib.sha256).hexdigest()


def verify_fenced_authenticated_persisted_process_transfer_restart(
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
    authentication_key: bytes,
    authentication_key_id: str,
    authentication_tag: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    fencing_authority_id: str,
    expected_previous_fencing_counter: int,
    requested_fencing_counter: int,
    claim_fencing_counter: Callable[[str, int, int], int],
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> FencedAuthenticatedProcessTransferRestartVerification:
    """Authenticate and externally claim the next fencing generation, then replay exact local restart evidence.

    The external compare-and-advance is intentionally performed before local replay. If the local replay later fails, the
    external generation remains consumed; MORPHEUS never treats that partial outcome as activation authority and never
    attempts to roll an external fencing service backward.
    """

    key = _require_authentication_key(authentication_key)
    authentication_key_id = _require_identity(authentication_key_id, "authentication_key_id")
    fencing_authority_id = _require_identity(fencing_authority_id, "fencing_authority_id")
    expected_previous_fencing_counter = _require_counter(
        expected_previous_fencing_counter, "expected_previous_fencing_counter"
    )
    requested_fencing_counter = _require_counter(requested_fencing_counter, "requested_fencing_counter")
    if requested_fencing_counter != expected_previous_fencing_counter + 1:
        raise ValueError("requested_fencing_counter must be exactly expected_previous_fencing_counter + 1")
    if not callable(claim_fencing_counter):
        raise ValueError("claim_fencing_counter must be callable")
    if not isinstance(authentication_tag, str) or len(authentication_tag) != 64 or any(
        ch not in "0123456789abcdef" for ch in authentication_tag
    ):
        raise ValueError("authentication_tag must be a lowercase HMAC-SHA256 hex digest")

    expected_tag = create_fenced_process_transfer_restart_authentication_tag(
        authentication_key=key,
        key_id=authentication_key_id,
        authority_id=expected_authority_id,
        sequence=expected_sequence,
        head_sha256=expected_head_sha256,
        fencing_authority_id=fencing_authority_id,
        previous_fencing_counter=expected_previous_fencing_counter,
        fencing_counter=requested_fencing_counter,
    )
    if not hmac.compare_digest(authentication_tag, expected_tag):
        raise ValueError("process-transfer fencing authentication tag does not match exact expected statement")

    try:
        claimed_fencing_counter = claim_fencing_counter(
            fencing_authority_id,
            expected_previous_fencing_counter,
            requested_fencing_counter,
        )
    except Exception as exc:
        raise ValueError("external fencing authority compare-and-advance failed") from exc
    claimed_fencing_counter = _require_counter(claimed_fencing_counter, "claimed_fencing_counter")
    if claimed_fencing_counter != requested_fencing_counter:
        raise ValueError("external fencing authority did not return the exact requested next counter")

    restart: ProcessTransferRestartVerification = verify_persisted_process_transfer_restart(
        head_path,
        bundle_path,
        expected_authority_id=expected_authority_id,
        expected_sequence=expected_sequence,
        expected_head_sha256=expected_head_sha256,
        expected_migration_id=expected_migration_id,
        expected_session_id=expected_session_id,
        expected_target_candidate_id=expected_target_candidate_id,
        expected_schema_identity=expected_schema_identity,
        expected_codec_identity=expected_codec_identity,
        expected_target_artifact_sha256=expected_target_artifact_sha256,
        expected_verification_manifest_sha256=expected_verification_manifest_sha256,
    )
    return FencedAuthenticatedProcessTransferRestartVerification(
        key_id=authentication_key_id,
        authority_id=restart.authority_id,
        sequence=restart.sequence,
        head_sha256=restart.head_sha256,
        bundle_sha256=restart.bundle_sha256,
        migration_id=restart.migration_id,
        session_id=restart.session_id,
        target_candidate_id=restart.target_candidate_id,
        fencing_authority_id=fencing_authority_id,
        previous_fencing_counter=expected_previous_fencing_counter,
        fencing_counter=claimed_fencing_counter,
    )
