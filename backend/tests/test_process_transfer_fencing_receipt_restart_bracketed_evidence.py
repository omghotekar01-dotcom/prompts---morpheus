from __future__ import annotations

import hashlib
import json

import pytest

from app.process_transfer_fencing_receipt_restart import BracketedFencedRestartCurrentnessVerification
from app.process_transfer_fencing_receipt_restart_bracketed_evidence import (
    encode_bracketed_restart_observation_receipt,
    verify_bracketed_restart_observation_receipt,
)


HEAD = "1" * 64
BUNDLE = "2" * 64
SOURCE_RECEIPT = "3" * 64


def _verification(**overrides) -> BracketedFencedRestartCurrentnessVerification:
    values = dict(
        receipt_sha256=SOURCE_RECEIPT,
        key_id="key-1",
        authority_id="receiver-a",
        sequence=7,
        head_sha256=HEAD,
        bundle_sha256=BUNDLE,
        migration_id="migration-7",
        session_id="session-7",
        target_candidate_id="candidate-b",
        fencing_authority_id="fence-a",
        previous_fencing_counter=40,
        fencing_counter=41,
        observed_fencing_counter_before=41,
        observed_fencing_counter_after=41,
    )
    values.update(overrides)
    return BracketedFencedRestartCurrentnessVerification(**values)


def _expected() -> dict[str, object]:
    return {
        "expected_source_receipt_sha256": SOURCE_RECEIPT,
        "expected_key_id": "key-1",
        "expected_authority_id": "receiver-a",
        "expected_sequence": 7,
        "expected_head_sha256": HEAD,
        "expected_bundle_sha256": BUNDLE,
        "expected_migration_id": "migration-7",
        "expected_session_id": "session-7",
        "expected_target_candidate_id": "candidate-b",
        "expected_fencing_authority_id": "fence-a",
        "expected_previous_fencing_counter": 40,
        "expected_fencing_counter": 41,
    }


def test_canonical_receipt_is_deterministic_and_replays_exact_bracketed_identity() -> None:
    first = encode_bracketed_restart_observation_receipt(_verification())
    second = encode_bracketed_restart_observation_receipt(_verification())
    assert first == second
    assert first.endswith(b"\n")

    result = verify_bracketed_restart_observation_receipt(first, **_expected())
    assert result.evidence_receipt_sha256 == hashlib.sha256(first).hexdigest()
    assert result.source_receipt_sha256 == SOURCE_RECEIPT
    assert result.observed_fencing_counter_before == 41
    assert result.observed_fencing_counter_after == 41
    assert result.historical_observation_binding_only is True
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
    assert "does not call the external fencing authority" in result.truth_boundary


def test_encoding_rejects_source_verification_with_unequal_observations() -> None:
    with pytest.raises(ValueError, match="observations must both equal fencing_counter"):
        encode_bracketed_restart_observation_receipt(_verification(observed_fencing_counter_after=42))


def test_encoding_rejects_any_authority_escalation() -> None:
    with pytest.raises(ValueError, match="activation_allowed must be false"):
        encode_bracketed_restart_observation_receipt(_verification(activation_allowed=True))


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("expected_source_receipt_sha256", "9" * 64),
        ("expected_authority_id", "receiver-b"),
        ("expected_sequence", 8),
        ("expected_head_sha256", "8" * 64),
        ("expected_bundle_sha256", "7" * 64),
        ("expected_migration_id", "migration-8"),
        ("expected_session_id", "session-8"),
        ("expected_target_candidate_id", "candidate-c"),
        ("expected_fencing_authority_id", "fence-b"),
        ("expected_previous_fencing_counter", 39),
        ("expected_fencing_counter", 42),
    ],
)
def test_replay_rejects_expected_identity_drift(field: str, wrong: object) -> None:
    encoded = encode_bracketed_restart_observation_receipt(_verification())
    expected = _expected()
    expected[field] = wrong
    with pytest.raises(ValueError):
        verify_bracketed_restart_observation_receipt(encoded, **expected)


def test_replay_rejects_tampered_observation_even_when_json_is_recanonicalized() -> None:
    encoded = encode_bracketed_restart_observation_receipt(_verification())
    payload = json.loads(encoded)
    payload["observed_fencing_counter_after"] = 42
    tampered = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ValueError, match="observations must both equal fencing_counter"):
        verify_bracketed_restart_observation_receipt(tampered, **_expected())


def test_replay_rejects_noncanonical_encoding() -> None:
    encoded = encode_bracketed_restart_observation_receipt(_verification())
    payload = json.loads(encoded)
    noncanonical = (json.dumps(payload, sort_keys=False, indent=2) + "\n").encode()
    with pytest.raises(ValueError, match="not canonical"):
        verify_bracketed_restart_observation_receipt(noncanonical, **_expected())


def test_replay_rejects_duplicate_json_keys() -> None:
    encoded = encode_bracketed_restart_observation_receipt(_verification())
    text = encoded.decode()
    duplicate = text.replace('{"activation_allowed":false,', '{"activation_allowed":false,"activation_allowed":false,', 1)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        verify_bracketed_restart_observation_receipt(duplicate.encode(), **_expected())


def test_receipt_replay_is_explicitly_historical_not_currentness_proof() -> None:
    encoded = encode_bracketed_restart_observation_receipt(_verification())
    result = verify_bracketed_restart_observation_receipt(encoded, **_expected())
    assert result.historical_observation_binding_only is True
    assert "prove that the fencing counter is current at replay time" in result.truth_boundary
    assert "safe cutover" in result.truth_boundary
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
