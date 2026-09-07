from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from .process_transfer_restart import ProcessTransferRestartVerification, verify_persisted_process_transfer_restart


AUTHENTICATED_RESTART_STATE = "VERIFIED_AUTHENTICATED_LOCAL_PROCESS_TRANSFER_RESTART_EVIDENCE_NO_ACTIVATION"
AUTHENTICATION_VERSION = "morpheus-process-transfer-restart-auth-v1"
TRUTH_BOUNDARY = (
    "This gate authenticates an exact restart expectation with HMAC-SHA256 under a caller-provisioned out-of-band secret "
    "and then replays the existing persisted-head and evidence-bundle restart verification. The authenticated statement "
    "binds version, key identifier, authority identifier, sequence and exact canonical head SHA-256. It does not store, "
    "provision, rotate, revoke or attest the secret; prove the key identifier itself is trustworthy; provide freshness, "
    "anti-replay, a trusted monotonic counter, rollback resistance, fencing, leases, consensus, distributed locking, "
    "crash/power-loss durability, process launch/replacement, activation/automatic-control authority, or performance, "
    "novelty, scientific-effect, HA/SLA, or production-readiness claims."
)

FRESH_AUTHENTICATED_RESTART_STATE = (
    "VERIFIED_EXTERNALLY_FRESH_AUTHENTICATED_LOCAL_PROCESS_TRANSFER_RESTART_EVIDENCE_NO_ACTIVATION"
)
FRESH_AUTHENTICATION_VERSION = "morpheus-process-transfer-restart-fresh-auth-v1"
FRESH_TRUTH_BOUNDARY = (
    "This gate binds an exact restart expectation to a caller-named external monotonic freshness authority and counter, "
    "authenticates that complete statement with HMAC-SHA256, requires a caller-supplied resolver to report the exact same "
    "current counter, and only then replays the existing persisted-head and evidence-bundle restart verification. A replay "
    "whose authenticated counter is behind an independently advanced resolver value is therefore rejected. MORPHEUS does "
    "not implement, authenticate, provision, persist, replicate or attest the external freshness authority or resolver; "
    "does not prove resolver liveness, correctness, atomicity or compromise resistance; and does not provide global "
    "freshness, distributed consensus, fencing, leases, distributed locking, crash/power-loss durability, process "
    "launch/replacement, activation/automatic-control authority, or performance, novelty, scientific-effect, HA/SLA, "
    "or production-readiness claims."
)


@dataclass(frozen=True)
class AuthenticatedProcessTransferRestartVerification:
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    authentication_verified: bool = True
    restart_evidence_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    evidence_state: str = AUTHENTICATED_RESTART_STATE
    truth_boundary: str = TRUTH_BOUNDARY


@dataclass(frozen=True)
class FreshAuthenticatedProcessTransferRestartVerification:
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    freshness_authority_id: str
    freshness_counter: int
    authentication_verified: bool = True
    external_freshness_verified: bool = True
    restart_evidence_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    evidence_state: str = FRESH_AUTHENTICATED_RESTART_STATE
    truth_boundary: str = FRESH_TRUTH_BOUNDARY


def _require_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a non-empty single-line string")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _require_authentication_key(value: Any) -> bytes:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ValueError("authentication_key must be at least 32 bytes")
    return value


def _require_counter(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _authentication_statement(*, key_id: str, authority_id: str, sequence: int, head_sha256: str) -> bytes:
    key_id = _require_identity(key_id, "key_id")
    authority_id = _require_identity(authority_id, "authority_id")
    head_sha256 = _require_sha256(head_sha256, "head_sha256")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    payload = {
        "authority_id": authority_id,
        "head_sha256": head_sha256,
        "key_id": key_id,
        "sequence": sequence,
        "version": AUTHENTICATION_VERSION,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _fresh_authentication_statement(
    *,
    key_id: str,
    authority_id: str,
    sequence: int,
    head_sha256: str,
    freshness_authority_id: str,
    freshness_counter: int,
) -> bytes:
    key_id = _require_identity(key_id, "key_id")
    authority_id = _require_identity(authority_id, "authority_id")
    head_sha256 = _require_sha256(head_sha256, "head_sha256")
    freshness_authority_id = _require_identity(freshness_authority_id, "freshness_authority_id")
    freshness_counter = _require_counter(freshness_counter, "freshness_counter")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    payload = {
        "authority_id": authority_id,
        "freshness_authority_id": freshness_authority_id,
        "freshness_counter": freshness_counter,
        "head_sha256": head_sha256,
        "key_id": key_id,
        "sequence": sequence,
        "version": FRESH_AUTHENTICATION_VERSION,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def create_process_transfer_restart_authentication_tag(
    *,
    authentication_key: bytes,
    key_id: str,
    authority_id: str,
    sequence: int,
    head_sha256: str,
) -> str:
    """Create a deterministic HMAC over an exact restart expectation; this is authentication, not freshness."""

    key = _require_authentication_key(authentication_key)
    statement = _authentication_statement(
        key_id=key_id,
        authority_id=authority_id,
        sequence=sequence,
        head_sha256=head_sha256,
    )
    return hmac.new(key, statement, hashlib.sha256).hexdigest()


def create_fresh_process_transfer_restart_authentication_tag(
    *,
    authentication_key: bytes,
    key_id: str,
    authority_id: str,
    sequence: int,
    head_sha256: str,
    freshness_authority_id: str,
    freshness_counter: int,
) -> str:
    """Authenticate an exact restart expectation plus an externally maintained monotonic freshness coordinate."""

    key = _require_authentication_key(authentication_key)
    statement = _fresh_authentication_statement(
        key_id=key_id,
        authority_id=authority_id,
        sequence=sequence,
        head_sha256=head_sha256,
        freshness_authority_id=freshness_authority_id,
        freshness_counter=freshness_counter,
    )
    return hmac.new(key, statement, hashlib.sha256).hexdigest()


def verify_authenticated_persisted_process_transfer_restart(
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
    authentication_key: bytes,
    authentication_key_id: str,
    authentication_tag: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> AuthenticatedProcessTransferRestartVerification:
    """Authenticate the exact expected local head, then perform the existing read-only restart replay gate."""

    key = _require_authentication_key(authentication_key)
    authentication_key_id = _require_identity(authentication_key_id, "authentication_key_id")
    if not isinstance(authentication_tag, str) or len(authentication_tag) != 64 or any(
        ch not in "0123456789abcdef" for ch in authentication_tag
    ):
        raise ValueError("authentication_tag must be a lowercase HMAC-SHA256 hex digest")

    expected_tag = create_process_transfer_restart_authentication_tag(
        authentication_key=key,
        key_id=authentication_key_id,
        authority_id=expected_authority_id,
        sequence=expected_sequence,
        head_sha256=expected_head_sha256,
    )
    if not hmac.compare_digest(authentication_tag, expected_tag):
        raise ValueError("process-transfer restart authentication tag does not match exact expected head statement")

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
    return AuthenticatedProcessTransferRestartVerification(
        key_id=authentication_key_id,
        authority_id=restart.authority_id,
        sequence=restart.sequence,
        head_sha256=restart.head_sha256,
        bundle_sha256=restart.bundle_sha256,
        migration_id=restart.migration_id,
        session_id=restart.session_id,
        target_candidate_id=restart.target_candidate_id,
    )


def verify_fresh_authenticated_persisted_process_transfer_restart(
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
    authentication_key: bytes,
    authentication_key_id: str,
    authentication_tag: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    freshness_authority_id: str,
    expected_freshness_counter: int,
    resolve_freshness_counter: Callable[[str], int],
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> FreshAuthenticatedProcessTransferRestartVerification:
    """Require authenticated external freshness before replaying persisted local restart evidence."""

    key = _require_authentication_key(authentication_key)
    authentication_key_id = _require_identity(authentication_key_id, "authentication_key_id")
    freshness_authority_id = _require_identity(freshness_authority_id, "freshness_authority_id")
    expected_freshness_counter = _require_counter(expected_freshness_counter, "expected_freshness_counter")
    if not callable(resolve_freshness_counter):
        raise ValueError("resolve_freshness_counter must be callable")
    if not isinstance(authentication_tag, str) or len(authentication_tag) != 64 or any(
        ch not in "0123456789abcdef" for ch in authentication_tag
    ):
        raise ValueError("authentication_tag must be a lowercase HMAC-SHA256 hex digest")

    expected_tag = create_fresh_process_transfer_restart_authentication_tag(
        authentication_key=key,
        key_id=authentication_key_id,
        authority_id=expected_authority_id,
        sequence=expected_sequence,
        head_sha256=expected_head_sha256,
        freshness_authority_id=freshness_authority_id,
        freshness_counter=expected_freshness_counter,
    )
    if not hmac.compare_digest(authentication_tag, expected_tag):
        raise ValueError("process-transfer fresh restart authentication tag does not match exact expected statement")

    try:
        observed_freshness_counter = resolve_freshness_counter(freshness_authority_id)
    except Exception as exc:
        raise ValueError("external freshness authority lookup failed") from exc
    observed_freshness_counter = _require_counter(observed_freshness_counter, "observed_freshness_counter")
    if observed_freshness_counter != expected_freshness_counter:
        relation = "stale" if observed_freshness_counter > expected_freshness_counter else "ahead of authority"
        raise ValueError(f"authenticated freshness counter is {relation}")

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
    return FreshAuthenticatedProcessTransferRestartVerification(
        key_id=authentication_key_id,
        authority_id=restart.authority_id,
        sequence=restart.sequence,
        head_sha256=restart.head_sha256,
        bundle_sha256=restart.bundle_sha256,
        migration_id=restart.migration_id,
        session_id=restart.session_id,
        target_candidate_id=restart.target_candidate_id,
        freshness_authority_id=freshness_authority_id,
        freshness_counter=expected_freshness_counter,
    )
